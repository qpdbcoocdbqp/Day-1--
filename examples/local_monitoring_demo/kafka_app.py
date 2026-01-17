import pathway as pw
import logging


# Set up logging
logging.basicConfig(level=logging.INFO)

class KafkaSchema(pw.Schema):
    id: int
    value: int
    timestamp: float

# Kafka configurations
# Assuming Kafka is running on localhost:9092 (standard for internal tools or Redpanda)
rdkafka_settings = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "pathway-monitoring-demo",
    "auto.offset.reset": "earliest",
}

# Read from Kafka using JSON format
# Pathway will automatically parse the JSON data based on KafkaSchema
table = pw.io.kafka.read(
    rdkafka_settings,
    topic="metrics",
    schema=KafkaSchema,
    format="json",
)

# Simple aggregation to demonstrate processing
# Calculating cumulative sum and count
result = table.reduce(
    total_sum=pw.reducers.sum(pw.this.value),
    record_count=pw.reducers.count(),
)

# Output results to null (monitoring will still show the activity)
pw.io.null.write(result)

# Run the pipeline with ALL monitoring level to see the TUI dashboard
logging.info("Starting Pathway Kafka ETL with local monitoring...")
pw.run(monitoring_level=pw.MonitoringLevel.ALL)
