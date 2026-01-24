# uv pip install kafka-python pyiceberg s3fs
import json
import time
import random
import os
import requests
from kafka import KafkaProducer


response = requests.get("http://localhost:8083/connectors")
if "events-sink" not in response.json():
    response = requests.post(
        "http://localhost:8083/connectors",
        json={
            "name": "events-sink",
            "config": {
                "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
                "tasks.max": "2",
                "topics": "events",
                "iceberg.tables": "default.events",
                "iceberg.catalog.type": "rest",
                "iceberg.catalog.uri": "http://iceberg:8181",
                "iceberg.catalog.warehouse": "s3://bucket/warehouse",
                "iceberg.catalog.client.region": "us-east-1",
                "iceberg.catalog.s3.endpoint": "http://minio:9000",
                "iceberg.catalog.s3.path-style-access": "true",
                "iceberg.catalog.s3.access-key-id": "minioadmin",
                "iceberg.catalog.s3.secret-access-key": "minioadmin",
            }
        })
    print(response.json())

response = requests.get("http://localhost:8083/connectors/events-sink/status")
print(response.json())
print(f"Connector 狀態: {response.status_code} - {response.text}")

# Configuration
KAFKA_CONFIG = {
    "bootstrap_servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092").split(","),
}

TOPIC = os.environ.get("KAFKA_TOPIC", "events")

# Sample event types
EVENT_TYPES = ["page_view", "click", "purchase", "signup", "logout"]

def generate_event(event_id: int) -> dict:
    """Generate a random event."""
    return {
        "event_id": event_id,
        "user_id": random.randint(1, 1000),
        "event_type": random.choice(EVENT_TYPES),
        "timestamp": time.time(),
        "value": round(random.uniform(0, 100), 2),
    }

producer = KafkaProducer(
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    **KAFKA_CONFIG
)

def main():
    """Main producer loop."""
    # producer = Producer(KAFKA_CONFIG)
    print(f"Producing events to Topic: `{TOPIC}` on {KAFKA_CONFIG['bootstrap_servers']}")
    event_id = 1
    try:
        while True:
            # Generate and send event
            event = generate_event(event_id)
            producer.send(TOPIC, value=event)
            print(f"Sent: {event}")
            event_id += 1
            # Wait before sending next event
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nShutting down producer...")
    finally:
        # Wait for any outstanding messages to be delivered
        producer.flush()
        print("Producer stopped.")


if __name__ == "__main__":
    main()
