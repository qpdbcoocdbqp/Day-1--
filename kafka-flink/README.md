# Kafka + Flink Trading Demo

A Python client sends trades to Kafka. Flink SQL calculates per-symbol statistics in 10-second event-time windows, and Druid ingests the results.

```text
mock-client → Kafka exchange.trades → Flink SQL → Kafka exchange.symbol-statistics → Druid
```

## Quick Start

Requires Docker Compose and about 6 GB of memory.

```bash
docker compose up --build -d
docker compose ps
```

Everything sets itself up: Kafka creates its topics, the JobManager submits the Flink SQL job ([flink/start-jobmanager.sh](flink/start-jobmanager.sh)), and the Druid router registers the Kafka supervisor ([druid/start-router.sh](druid/start-router.sh)). To submit the Flink job again, run `docker compose restart jobmanager`.

Read the Flink output:

```bash
docker compose run --rm mock-client consume --from-beginning
```

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
| Flink | http://localhost:8081 | Jobs, TaskManagers, checkpoints |
| Druid | http://localhost:8888 | SQL queries, ingestion status |
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
