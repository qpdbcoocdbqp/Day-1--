# Copyright © 2026 Pathway

import json
import os
import random
import time
from confluent_kafka import Producer

topic = "linear-regression"

random.seed(0)
# function that creates a floating number close in value to i
def get_value(i):
    return i + (2 * random.random() - 1) / 10

# set kafka credentials
kafka_endpoint = os.getenv("KAFKA_BOOTSTRAP_SERVERS")

# generate input stream
# confluent_kafka uses librdkafka style config (dot-separated keys)
producer = Producer({
    'bootstrap.servers': kafka_endpoint,
})

# send Kafka messages with i (x) and float close to i (y)
for i in range(120):
    time.sleep(1)
    payload = {
        "x": i,
        "y": get_value(i),
    }
    producer.produce(topic, json.dumps(payload).encode("utf-8"))
    producer.flush()  # ensure message is sent
    print(f"Sent message {i}")

# close stream (flush remaining messages)
producer.flush()
print("Done!")