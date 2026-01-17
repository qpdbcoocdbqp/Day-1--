import time
import json
import random
import logging
from confluent_kafka import Producer


logging.basicConfig(level=logging.INFO)

def delivery_report(err, msg):
    if err is not None:
        logging.error(f'Message delivery failed: {err}')
    else:
        logging.info(f'Message delivered to {msg.topic()} [{msg.partition()}]')

def main():
    # Bootstrap servers should match the Kafka/Redpanda address
    conf = {'bootstrap.servers': 'localhost:9092'}
    producer = Producer(conf)
    topic = 'metrics'

    logging.info(f"Starting to produce messages to topic: {topic}")
    counter = 0
    try:
        while True:
            data = {
                'id': counter,
                'value': random.randint(0, 100),
                'timestamp': time.time()
            }
            producer.produce(topic, json.dumps(data).encode('utf-8'), callback=delivery_report)
            producer.poll(0)
            counter += 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info("Stopping producer...")
    finally:
        producer.flush()

if __name__ == '__main__':
    main()
