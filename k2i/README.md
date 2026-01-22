docker compose up -d
docker exec -it redpanda rpk topic create events

curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d '{
  "name": "iceberg-sink",
  "config": {
    "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
    "topics": "events",
    "iceberg.catalog.type": "rest",
    "iceberg.catalog.uri": "http://iceberg-rest:8181",
    "iceberg.catalog.warehouse": "s3://warehouse",
    "iceberg.catalog.s3.endpoint": "http://minio:9000",
    "iceberg.catalog.s3.path-style-access": "true",
    "iceberg.catalog.client.region": "us-east-1",
    "iceberg.catalog.client.credentials": "admin:password123",
    "iceberg.tables": "db.events_table",
    "iceberg.tables.auto-create": "true",
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "key.converter.schemas.enable": "false",
    "value.converter.schemas.enable": "false"
  }
}'
