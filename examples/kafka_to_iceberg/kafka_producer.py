"""
Kafka Producer for Testing
===========================

This script produces sample events to Kafka for testing the Kafka to Iceberg pipeline.

Usage:
    python kafka_producer.py

Environment Variables:
    KAFKA_BOOTSTRAP_SERVERS: Kafka broker address (default: localhost:9092)
    KAFKA_TOPIC: Topic to produce to (default: events)
"""

import json
import time
import random
import os

from confluent_kafka import Producer


# Configuration
KAFKA_CONFIG = {
    "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
}

TOPIC = os.environ.get("KAFKA_TOPIC", "events")

# Sample event types
EVENT_TYPES = ["page_view", "click", "purchase", "signup", "logout"]


def delivery_callback(err, msg):
    """Callback for message delivery reports."""
    if err:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")


def generate_event(event_id: int) -> dict:
    """Generate a random event."""
    return {
        "event_id": event_id,
        "user_id": random.randint(1, 1000),
        "event_type": random.choice(EVENT_TYPES),
        "timestamp": time.time(),
        "value": round(random.uniform(0, 100), 2),
    }


def main():
    """Main producer loop."""
    producer = Producer(KAFKA_CONFIG)
    print(f"Producing events to {TOPIC} on {KAFKA_CONFIG['bootstrap.servers']}")

    event_id = 1
    try:
        while True:
            # Generate and send event
            event = generate_event(event_id)
            message = json.dumps(event)

            producer.produce(
                topic=TOPIC,
                value=message.encode("utf-8"),
                callback=delivery_callback,
            )

            # Process delivery callbacks
            producer.poll(0)

            print(f"Sent: {event}")
            event_id += 1

            # Wait before sending next event
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down producer...")
    finally:
        # Wait for any outstanding messages to be delivered
        producer.flush()
        print("Producer stopped.")


if __name__ == "__main__":
    main()
