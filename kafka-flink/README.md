# Kafka + Flink Trading Demo

This demo generates trades with Python, sends them to Kafka, and uses Flink SQL to calculate per-symbol statistics in 10-second event-time windows.

```text
mock-client → Kafka exchange.trades → Flink SQL → exchange.symbol-statistics
```

## Quick Start

Requirements: Docker Compose and about 3 GB of available memory.

```bash
cd kafka-flink
docker compose up --build -d
docker compose ps
```

Submit the Flink SQL job:

```bash
docker compose exec jobmanager /bin/bash /opt/flink/usrlib/submit-job.sh
```

The JobManager submits the SQL job directly, so no separate `flink-job` container is needed. The script skips submission if the job is already running.

Read the Flink output:

```bash
docker compose run --rm mock-client consume --from-beginning
```

## Monitoring

| Service | URL | Purpose |
| --- | --- | --- |
| Flink | http://localhost:8081 | Jobs, TaskManagers, and checkpoints |
| Grafana | http://localhost:3000 | Kafka and Flink dashboards |
| Prometheus | http://localhost:9090 | Metrics and alerts |
| Kafka exporter | http://localhost:9308/metrics | Consumer lag metrics |
| Statistics metrics | http://localhost:8000/metrics | Latest `exchange.symbol-statistics` values |

Grafana includes two dashboards:

- **Kafka and Flink Overview**: consumer lag, TaskManager status, and Flink records per second.
- **Exchange Symbol Statistics**: current prices, trade counts, quantities, and historical trends by symbol.

The `mock-client` reads `exchange.symbol-statistics` and exposes the results as Prometheus gauges. No extra container is required. Prometheus stores sampled trends, not every record from the Kafka topic.

## Single-Host Recovery

Flink creates a checkpoint every 10 seconds. Checkpoints and savepoints are stored in Docker named volumes. After a short JobManager or TaskManager failure, Flink restarts and restores the latest checkpoint. Kafka keeps topics and consumer offsets.

Create a savepoint before a full shutdown or deployment if the Flink window state must be preserved:

```bash
# Find the job ID
docker compose exec jobmanager flink list

# Replace <JOB_ID> with the actual ID
docker compose exec jobmanager flink savepoint <JOB_ID> file:///opt/flink/savepoints/manual
```

Checkpoints support automatic runtime recovery. Savepoints support full restarts, deployments, and manual recovery. Submit the SQL job again after a complete `down/up` cycle.

```bash
# Restart while keeping Kafka and Flink data
docker compose down
docker compose up -d
docker compose exec jobmanager /bin/bash /opt/flink/usrlib/submit-job.sh

# Delete all data and rebuild from scratch (cannot be undone)
docker compose down -v --remove-orphans
docker compose up --build -d
docker compose exec jobmanager /bin/bash /opt/flink/usrlib/submit-job.sh
```

`down -v` deletes the Kafka, checkpoint, savepoint, Prometheus, and Grafana volumes. The current setup uses 10-second checkpoints, up to 10 restart attempts, and a Kafka exactly-once sink.

## Trade Data Format

Records in `exchange.trades` use this format:

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

Flink writes trade counts, buy and sell quantities, and price statistics to `exchange.symbol-statistics`.

## Useful Commands

```bash
# View Flink logs and job status
docker compose logs -f jobmanager taskmanager
docker compose exec jobmanager flink list

# Stop services while keeping named volumes
docker compose down
```

`flink-storage-init` and `kafka-init` are one-time setup services. `Exited (0)` means they completed successfully.

External clients can reach Kafka at `localhost:29092`. Configure the client with `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_INPUT_TOPIC`, and `KAFKA_OUTPUT_TOPIC`.
