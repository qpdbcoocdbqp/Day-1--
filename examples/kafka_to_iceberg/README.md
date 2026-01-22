# Kafka to Iceberg ETL with Pathway

This example demonstrates how to build a real-time ETL pipeline that reads data from Kafka and writes to Apache Iceberg using Pathway.

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Kafka     │───▶│   Pathway   │───▶│   Iceberg   │───▶│    MinIO    │
│  (Redpanda) │    │   Pipeline  │    │ REST Catalog│    │  (Storage)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Pathway license (for Iceberg connector)

## Quick Start

### 1. Start Infrastructure

```bash
docker-compose up -d
```

This will start:
- **Redpanda** (Kafka-compatible) on `localhost:9092`
- **MinIO** (S3-compatible storage) on `localhost:9000`
- **Iceberg REST Catalog** on `localhost:8181`

### 2. Create Kafka Topic

```bash
docker exec -it redpanda rpk topic create events
```

### 3. Install Dependencies

```bash
pip install pathway confluent-kafka
```

### 4. Start the Pathway Pipeline

```bash
python kafka_to_iceberg.py
```

### 5. Send Test Events

In another terminal:

```bash
python kafka_producer.py

docker compose --profile producer up -d
```

## Configuration

### Environment Variables

| Variable                  | Default                 | Description              |
| ------------------------- | ----------------------- | ------------------------ |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092`        | Kafka broker address     |
| `KAFKA_TOPIC`             | `events`                | Kafka topic to consume   |
| `ICEBERG_CATALOG_URI`     | `http://localhost:8181` | Iceberg REST catalog URI |

## Files

| File                  | Description               |
| --------------------- | ------------------------- |
| `kafka_to_iceberg.py` | Main Pathway ETL pipeline |
| `kafka_producer.py`   | Test data producer        |
| `docker-compose.yaml` | Infrastructure setup      |

## Viewing Data in Iceberg

### Using PyIceberg

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    name="default",
    uri="http://localhost:8181",
)

table = catalog.load_table("data_lake.events")
df = table.scan().to_pandas()
print(df)
```

### Using MinIO Console

1. Open http://localhost:9001
2. Login with `admin` / `password123`
3. Browse the `warehouse` bucket

## Notes

- The Iceberg connector requires a valid Pathway license with Iceberg entitlements
- The `min_commit_frequency` parameter controls how often data is committed to Iceberg
- The namespace and table are created automatically if they don't exist
