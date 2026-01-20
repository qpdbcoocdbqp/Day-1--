"""
Kafka to Iceberg ETL Pipeline using Pathway
=============================================

This example demonstrates how to read data from Kafka and write it to Apache Iceberg
using Pathway's streaming processing capabilities.

Prerequisites:
- Kafka/Redpanda running on localhost:9092
- Iceberg REST catalog running on localhost:8181
- Required Python packages: pathway

Usage:
    python kafka_to_iceberg.py

Environment Variables:
    KAFKA_BOOTSTRAP_SERVERS: Kafka broker address (default: localhost:9092)
    ICEBERG_CATALOG_URI: Iceberg REST catalog URI (default: http://localhost:8181)
"""

import os
import logging

import pathway as pw

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Schema Definition
# =============================================================================

class EventSchema(pw.Schema):
    """
    Schema for events consumed from Kafka.
    Define primary_key for Iceberg write operations.
    """
    event_id: int = pw.column_definition(primary_key=True)
    user_id: int
    event_type: str
    timestamp: float
    value: float


# =============================================================================
# Configuration
# =============================================================================

# Kafka Configuration
KAFKA_SETTINGS = {
    "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "group.id": "pathway-kafka-to-iceberg",
    "auto.offset.reset": "earliest",
}

KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "events")

# Iceberg Configuration
ICEBERG_CATALOG_URI = os.environ.get("ICEBERG_CATALOG_URI", "http://localhost:8181")
ICEBERG_NAMESPACE = ["data_lake"]
ICEBERG_TABLE_NAME = "events"


# =============================================================================
# Pipeline Definition
# =============================================================================

def create_kafka_to_iceberg_pipeline():
    """
    Create a streaming pipeline that reads from Kafka and writes to Iceberg.
    """
    logger.info(f"Starting Kafka to Iceberg pipeline")
    logger.info(f"Kafka: {KAFKA_SETTINGS['bootstrap.servers']} / Topic: {KAFKA_TOPIC}")
    logger.info(f"Iceberg: {ICEBERG_CATALOG_URI} / {'.'.join(ICEBERG_NAMESPACE)}.{ICEBERG_TABLE_NAME}")

    # Read from Kafka
    # The connector will parse JSON messages according to the EventSchema
    kafka_table = pw.io.kafka.read(
        KAFKA_SETTINGS,
        topic=KAFKA_TOPIC,
        schema=EventSchema,
        format="json",
    )

    # Optional: Add some transformations
    # Example: Add a processed_at timestamp
    processed_table = kafka_table.select(
        event_id=pw.this.event_id,
        user_id=pw.this.user_id,
        event_type=pw.this.event_type,
        timestamp=pw.this.timestamp,
        value=pw.this.value,
    )

    if not os.environ.get("PATHWAY_LICENSE_KEY"):
        logger.warning("PATHWAY_LICENSE_KEY is not set. The Iceberg connector requires a Pathway license.")
        logger.warning("Switching to debug output (printing to console).")
        logger.warning("To use Iceberg, obtain a license at https://pathway.com/get-license/")
        pw.debug.compute_and_print(processed_table)
    else:
        # Configure Iceberg REST Catalog
        iceberg_catalog = pw.io.iceberg.RestCatalog(
            uri=ICEBERG_CATALOG_URI,
        )

        # Write to Iceberg
        # The connector will create the namespace and table if they don't exist
        pw.io.iceberg.write(
            processed_table,
            catalog=iceberg_catalog,
            namespace=ICEBERG_NAMESPACE,
            table_name=ICEBERG_TABLE_NAME,
            min_commit_frequency=5_000,  # Commit every 5 seconds
        )

    logger.info("Pipeline configured successfully")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Create the pipeline
    create_kafka_to_iceberg_pipeline()

    # Run the pipeline
    logger.info("Starting Pathway runtime...")
    pw.run(monitoring_level=pw.MonitoringLevel.ALL)
