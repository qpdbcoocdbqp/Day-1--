"""Web UI for the Flink window statistics stored in ClickHouse or Druid.

OLAP_BACKEND picks the store. Both are queried over their HTTP SQL APIs, so the backends differ only
in SQL dialect and response shape.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


TABLE = "exchange_symbol_statistics"
TIMEOUT_SECONDS = 15
SQL_CONSOLE_MAX_ROWS = 1000
SERIES_MAX_ROWS = 20_000
MAX_BUCKETS = 120
BUCKET_LADDER_SECONDS = (10, 30, 60, 180, 300, 600, 900, 1800, 3600)
PRICE_FIELDS = ("low_price", "high_price", "average_price", "buy_quantity", "sell_quantity")


class BackendError(Exception):
    """The OLAP store rejected the query or could not be reached."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool


def open_url(request: urllib.request.Request, describe_error) -> urllib.request.addinfourl:
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        raise BackendError(describe_error(exc.read().decode("utf-8", "replace").strip()) or str(exc)) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise BackendError(f"Cannot reach {request.full_url.split('?')[0]}: {getattr(exc, 'reason', exc)}") from exc


class ClickHouse:
    name = "ClickHouse"
    example_query = f"""SELECT
    symbol,
    count() AS windows,
    sum(trade_count) AS trades,
    round(avg(average_price), 2) AS avg_price,
    max(window_start) AS latest_window
FROM {TABLE} FINAL
GROUP BY symbol
ORDER BY symbol"""

    def __init__(self) -> None:
        self.url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123").rstrip("/")
        self.headers = {
            "X-ClickHouse-User": os.getenv("CLICKHOUSE_USER", "default"),
            "X-ClickHouse-Key": os.getenv("CLICKHOUSE_PASSWORD", ""),
        }

    def query(self, sql: str, max_rows: int) -> QueryResult:
        # readonly=2 rejects writes but still lets these URL settings apply. The row cap is enforced
        # while streaming, because max_result_rows would also truncate subqueries.
        settings = {
            "default_format": "JSONCompactEachRowWithNames",
            "readonly": 2,
            "max_execution_time": TIMEOUT_SECONDS,
            "cancel_http_readonly_queries_on_client_close": 1,
            "http_write_exception_in_output_format": 0,
        }
        request = urllib.request.Request(
            f"{self.url}/?{urllib.parse.urlencode(settings)}", data=sql.encode("utf-8"), headers=self.headers
        )
        with open_url(request, lambda body: body) as response:
            lines = (line for line in response if line.strip())
            columns = self._parse_line(next(lines, b"[]"))
            rows = []
            for line in lines:
                if len(rows) == max_rows:
                    return QueryResult(columns, rows, truncated=True)
                rows.append(self._parse_line(line))
        return QueryResult(columns, rows, truncated=False)

    @staticmethod
    def _parse_line(line: bytes) -> list:
        # Errors raised after streaming has started arrive as plain text instead of an HTTP status.
        text = line.decode("utf-8", "replace").strip()
        try:
            value = json.loads(text)
        except ValueError:
            raise BackendError(text if "Exception" in text else "Remove the FORMAT clause; the UI reads JSON rows.")
        if not isinstance(value, list):
            raise BackendError("Remove the FORMAT clause; the UI reads JSON rows.")
        return value

    def series_sql(self, minutes: int, bucket_seconds: int) -> str:
        # ClickHouse resolves names to aliases first, so `trade_count` inside the weighted average would
        # mean sum(trade_count); prefer_column_name_to_alias makes it the column again.
        return f"""
SELECT
    symbol,
    toUnixTimestamp(toStartOfInterval(toDateTime(window_start), INTERVAL {bucket_seconds} SECOND)) * 1000 AS t,
    sum(trade_count) AS trade_count,
    min(low_price) AS low_price,
    max(high_price) AS high_price,
    sum(toFloat64(average_price) * trade_count) / sum(trade_count) AS average_price,
    sum(buy_quantity) AS buy_quantity,
    sum(sell_quantity) AS sell_quantity
FROM {TABLE} FINAL
WHERE window_start >= now64(3) - INTERVAL {minutes} MINUTE
GROUP BY symbol, t
ORDER BY t, symbol
SETTINGS prefer_column_name_to_alias = 1"""


class Druid:
    name = "Druid"
    example_query = f"""SELECT
  symbol,
  COUNT(*) AS windows,
  SUM(trade_count) AS trades,
  ROUND(AVG(average_price), 2) AS avg_price,
  MAX(__time) AS latest_window
FROM {TABLE}
GROUP BY symbol
ORDER BY symbol"""

    def __init__(self) -> None:
        self.url = os.getenv("DRUID_URL", "http://router:8888").rstrip("/")

    def query(self, sql: str, max_rows: int) -> QueryResult:
        payload = {
            "query": sql,
            "resultFormat": "array",
            "header": True,
            # sqlOuterLimit caps only the outermost query, so one extra row reveals truncation.
            "context": {"sqlOuterLimit": max_rows + 1, "sqlTimeZone": "Etc/UTC", "timeout": TIMEOUT_SECONDS * 1000},
        }
        request = urllib.request.Request(
            f"{self.url}/druid/v2/sql",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with open_url(request, self._error_message) as response:
            result = json.load(response)
        columns, rows = (result[0], result[1:]) if result else ([], [])
        return QueryResult(columns, rows[:max_rows], truncated=len(rows) > max_rows)

    @staticmethod
    def _error_message(body: str) -> str:
        try:
            error = json.loads(body)
        except ValueError:
            return body
        return error.get("errorMessage") or error.get("error") or body

    def series_sql(self, minutes: int, bucket_seconds: int) -> str:
        return f"""
SELECT
  symbol,
  TIMESTAMP_TO_MILLIS(TIME_FLOOR(__time, '{iso_period(bucket_seconds)}')) AS t,
  SUM(trade_count) AS trade_count,
  MIN(low_price) AS low_price,
  MAX(high_price) AS high_price,
  SUM(average_price * trade_count) / SUM(trade_count) AS average_price,
  SUM(buy_quantity) AS buy_quantity,
  SUM(sell_quantity) AS sell_quantity
FROM {TABLE}
WHERE __time >= CURRENT_TIMESTAMP - INTERVAL '{minutes}' MINUTE
GROUP BY 1, 2
ORDER BY 2, 1"""


def iso_period(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"PT{seconds // 3600}H"
    if seconds % 60 == 0:
        return f"PT{seconds // 60}M"
    return f"PT{seconds}S"


def bucket_for(minutes: int) -> int:
    """Smallest bucket that keeps the chart at or under MAX_BUCKETS columns."""
    for seconds in BUCKET_LADDER_SECONDS:
        if minutes * 60 / seconds <= MAX_BUCKETS:
            return seconds
    return BUCKET_LADDER_SECONDS[-1]


BACKENDS = {"clickhouse": ClickHouse, "druid": Druid}
BACKEND_KEY = os.getenv("OLAP_BACKEND", "clickhouse").strip().lower()
if BACKEND_KEY not in BACKENDS:
    raise SystemExit(f"OLAP_BACKEND must be one of {', '.join(BACKENDS)}; got {BACKEND_KEY!r}")
backend = BACKENDS[BACKEND_KEY]()

app = FastAPI(title="Exchange statistics UI")


class SqlRequest(BaseModel):
    query: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "backend": BACKEND_KEY}


@app.get("/api/info")
def info() -> dict:
    return {"backend": BACKEND_KEY, "name": backend.name, "table": TABLE, "example_query": backend.example_query}


@app.get("/api/series")
def series(minutes: int = Query(15, ge=1, le=1440)) -> dict:
    bucket_seconds = bucket_for(minutes)
    try:
        result = backend.query(backend.series_sql(minutes, bucket_seconds), SERIES_MAX_ROWS)
    except BackendError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    points = []
    for values in result.rows:
        row = dict(zip(result.columns, values))
        points.append(
            {
                "symbol": row["symbol"],
                "t": int(row["t"]),
                "trade_count": int(row["trade_count"]),
                **{field: float(row[field]) for field in PRICE_FIELDS},
            }
        )
    return {"now": int(time.time() * 1000), "minutes": minutes, "bucket_seconds": bucket_seconds, "rows": points}


@app.post("/api/sql")
def run_sql(request: SqlRequest) -> dict:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Enter a query.")
    started = time.perf_counter()
    try:
        result = backend.query(request.query, SQL_CONSOLE_MAX_ROWS)
    except BackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "columns": result.columns,
        "rows": result.rows,
        "truncated": result.truncated,
        "max_rows": SQL_CONSOLE_MAX_ROWS,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
