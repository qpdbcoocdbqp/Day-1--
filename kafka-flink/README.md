# Kafka + Flink Trading Demo

A Python client sends trades to Kafka. Flink SQL calculates per-symbol statistics in 10-second event-time windows, an OLAP store (ClickHouse or Druid) ingests the results, and a web UI charts and queries them.

```text
mock-client → Kafka exchange.trades → Flink SQL → Kafka exchange.symbol-statistics → ClickHouse or Druid → UI
```

## Quick Start

Requires Docker Compose. With ClickHouse the stack needs about 3 GB of memory; with Druid about 6 GB.

```bash
docker compose up --build -d
docker compose ps
```

Open the UI at http://localhost:8080.

Everything sets itself up: Kafka creates its topics, the JobManager submits the Flink SQL job ([flink/start-jobmanager.sh](flink/start-jobmanager.sh)), ClickHouse creates its tables from [clickhouse/init.sql](clickhouse/init.sql), and the Druid router registers the Kafka supervisor ([druid/start-router.sh](druid/start-router.sh)). To submit the Flink job again, run `docker compose restart jobmanager`.

Read the Flink output:

```bash
docker compose run --rm mock-client consume --from-beginning
```

## Choosing ClickHouse or Druid

[.env](.env) picks the OLAP store:

```dotenv
OLAP_BACKEND=clickhouse   # or druid
COMPOSE_PROFILES=${OLAP_BACKEND}
```

`COMPOSE_PROFILES` starts only that store's services, and the UI reads `OLAP_BACKEND` to decide which one to query. Stop the stack before switching so the other store's containers are removed:

```bash
docker compose down
# edit OLAP_BACKEND in .env
docker compose up -d
```

Each store keeps its own volumes, so switching back shows the data it stored before.

| | ClickHouse | Druid |
| --- | --- | --- |
| Containers | 1 | 7 (ZooKeeper, PostgreSQL, coordinator, broker, historical, middleManager, router) |
| Memory in this demo | about 550 MB | about 2.9 GB |
| Reads Kafka with | Kafka table engine and a materialized view | Kafka supervisor |
| Delivery | At-least-once; `ReplacingMergeTree` collapses duplicates, so query with `FINAL` | Exactly-once |
| Console | http://localhost:8123/play (user and password `clickhouse`) | http://localhost:8888 |

## UI

http://localhost:8080 shows:

- The latest window for each symbol, with the change from the previous window.
- Average price with its low–high range, and buy versus sell quantity, for one symbol over 5 minutes to 6 hours. Longer ranges are rolled up into larger buckets so a chart never has more than 120 points.
- A table of the plotted values.
- A SQL console. Queries are read-only: ClickHouse runs them with `readonly=2`, and Druid's SQL endpoint does not run `INSERT`. Only the first 1,000 rows are returned.

[ui/app.py](ui/app.py) queries the store over its HTTP SQL API; [ui/static/](ui/static/) is plain HTML and JavaScript with no CDN dependencies.

## ClickHouse

Like Druid, ClickHouse reads `exchange.symbol-statistics` itself, so the Flink job is the same for both stores. In [clickhouse/init.sql](clickhouse/init.sql), the `exchange_symbol_statistics_queue` table (Kafka engine) consumes the topic, and a materialized view copies each batch into `exchange_symbol_statistics`.

```sql
SELECT window_start, symbol, trade_count, average_price
FROM exchange_symbol_statistics FINAL
ORDER BY window_start DESC
LIMIT 20
```

`init.sql` runs only when the `clickhouse-data` volume is empty. To apply schema changes, remove that volume and start ClickHouse again.

## Druid

Flink has no native Druid sink, so Druid reads the `exchange.symbol-statistics` topic with the supervisor in [druid/supervisor-spec.json](druid/supervisor-spec.json). Query it in the console at http://localhost:8888:

```sql
SELECT __time, symbol, trade_count, average_price
FROM exchange_symbol_statistics
ORDER BY __time DESC
LIMIT 20
```

## Monitoring

| Service | URL | Purpose |
| --- | --- | --- |
| UI | http://localhost:8080 | Symbol statistics and SQL console |
| Flink | http://localhost:8081 | Jobs, TaskManagers, checkpoints |
| ClickHouse | http://localhost:8123/play | SQL queries (ClickHouse mode) |
| Druid | http://localhost:8888 | SQL queries, ingestion status (Druid mode) |
| Grafana | http://localhost:3000 | Kafka, Flink, and symbol statistics dashboards |
| Prometheus | http://localhost:9090 | Metrics and alerts |
| Kafka exporter | http://localhost:9308/metrics | Consumer lag |
| Statistics metrics | http://localhost:8000/metrics | Latest `exchange.symbol-statistics` values |

## Recovery

Flink checkpoints every 10 seconds into Docker named volumes.

- **TaskManager failure**: Flink restores the latest checkpoint.
- **JobManager restart or full `down/up`**: the SQL job is submitted again as a new job. It resumes from the Kafka consumer offsets, but unfinished window state is lost.

To keep window state across a shutdown, create a savepoint first:

```bash
docker compose exec jobmanager flink list
docker compose exec jobmanager flink savepoint <JOB_ID> file:///opt/flink/savepoints/manual
```

```bash
# Restart and keep data
docker compose down
docker compose up -d

# Delete all volumes and rebuild (cannot be undone)
docker compose down -v --remove-orphans
docker compose up --build -d
```

## Data Format

Records in `exchange.trades`:

```json
{
  "trade_id": "5ed22f18-8728-48e3-8e00-c446748d39f0",
  "symbol": "BTC-USD",
  "side": "BUY",
  "price": 67542.1256,
  "quantity": 0.1842,
  "event_time": "2026-09-25 14:03:27.481"
}
```

`exchange.symbol-statistics` holds the trade count, buy and sell quantities, and price statistics for each symbol and window.

External clients reach Kafka at `localhost:29092`. Configure them with `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_INPUT_TOPIC`, and `KAFKA_OUTPUT_TOPIC`.
