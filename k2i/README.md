

```sh
curl -L -o ./connectors/iceberg-kafka-connect-runtime-0.6.1.jar https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-kafka-connect-runtime/0.6.1/iceberg-kafka-connect-runtime-0.6.1.jar


curl -L -o ./iceberg-kafka-connect-runtime-0.6.1.jar https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-kafka-connect-runtime/0.6.1/iceberg-kafka-connect-runtime-0.6.1.jar

docker compose up -d
docker exec -it redpanda rpk topic create events

<!-- curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d '{
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
}' -->

curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d '{
  "name": "iceberg-sink",
  "config": {
    "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
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

curl -s http://localhost:8083/connectors/iceberg-sink/status

docker exec -i redpanda rpk topic produce events <<EOF
{"id": 1, "name": "test_data", "amount": 100.5, "status": "active"}
{"id": 2, "name": "iceberg_demo", "amount": 200.0, "status": "pending"}
EOF
```

---

```sh
cd k2i
git clone https://github.com/apache/iceberg.git
cd iceberg
./gradlew build -x checkstyleMain -x checkstyleTest
./gradlew spotlessApply

./gradlew :iceberg-kafka-connect:iceberg-kafka-connect-runtime:build -x checkstyleMain -x checkstyleTest
./gradlew spotlessApply

curl http://localhost:8083/connectors
curl http://localhost:8083/connector-plugins

curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "events-sink",
    "config": {
      "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
      "tasks.max": "2",
      "topics": "events",
      "iceberg.tables": "default.events",
      "iceberg.catalog.type": "rest",
      "iceberg.catalog.uri": "http://iceberg:8181",
      "iceberg.catalog.warehouse": "s3://bucket/warehouse"
    }
  }'

curl http://localhost:8083/connectors/events-sink/status
```