import argparse
import json
import os
import random
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, Producer
from prometheus_client import Gauge, start_http_server


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "exchange.trades")
OUTPUT_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC", "exchange.symbol-statistics")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))

STAT_AVERAGE_PRICE = Gauge("exchange_symbol_average_price", "Latest window average price", ["symbol"])
STAT_LOW_PRICE = Gauge("exchange_symbol_low_price", "Latest window low price", ["symbol"])
STAT_HIGH_PRICE = Gauge("exchange_symbol_high_price", "Latest window high price", ["symbol"])
STAT_TRADE_COUNT = Gauge("exchange_symbol_trade_count", "Trades in the latest window", ["symbol"])
STAT_TOTAL_QUANTITY = Gauge("exchange_symbol_total_quantity", "Total quantity in the latest window", ["symbol"])
STAT_BUY_QUANTITY = Gauge("exchange_symbol_buy_quantity", "Buy quantity in the latest window", ["symbol"])
STAT_SELL_QUANTITY = Gauge("exchange_symbol_sell_quantity", "Sell quantity in the latest window", ["symbol"])
STAT_WINDOW_END = Gauge("exchange_symbol_window_end_timestamp_seconds", "Latest completed window end", ["symbol"])

REFERENCE_PRICES = {
    "BTC-USD": 67_500.0,
    "ETH-USD": 3_450.0,
    "SOL-USD": 145.0,
    "AAPL": 225.0,
}


def build_trade(prices: dict[str, float]) -> dict:
    symbol = random.choice(list(prices))
    prices[symbol] = max(0.01, prices[symbol] * (1 + random.gauss(0, 0.0008)))

    return {
        "trade_id": str(uuid.uuid4()),
        "symbol": symbol,
        "side": random.choice(["BUY", "SELL"]),
        "price": round(prices[symbol], 4),
        "quantity": round(random.uniform(0.01, 3.0), 6),
        "event_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
    }


def wait_for_broker(config: dict, attempts: int = 30) -> None:
    producer = Producer(config)
    for attempt in range(1, attempts + 1):
        try:
            producer.list_topics(timeout=3)
            return
        except Exception as exc:
            if attempt == attempts:
                raise RuntimeError(f"Kafka is unavailable at {BOOTSTRAP_SERVERS}") from exc
            print(f"Waiting for Kafka ({attempt}/{attempts})...", flush=True)
            time.sleep(2)


def export_statistics(stop_event: threading.Event) -> None:
    config = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "exchange-statistics-metrics",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
        "isolation.level": "read_committed",
    }
    consumer = Consumer(config)
    consumer.subscribe([OUTPUT_TOPIC])
    try:
        while not stop_event.is_set():
            message = consumer.poll(1.0)
            if message is None or message.error():
                continue
            record = json.loads(message.value().decode("utf-8"))
            symbol = record["symbol"]
            STAT_AVERAGE_PRICE.labels(symbol).set(float(record["average_price"]))
            STAT_LOW_PRICE.labels(symbol).set(float(record["low_price"]))
            STAT_HIGH_PRICE.labels(symbol).set(float(record["high_price"]))
            STAT_TRADE_COUNT.labels(symbol).set(float(record["trade_count"]))
            STAT_TOTAL_QUANTITY.labels(symbol).set(float(record["total_quantity"]))
            STAT_BUY_QUANTITY.labels(symbol).set(float(record["buy_quantity"]))
            STAT_SELL_QUANTITY.labels(symbol).set(float(record["sell_quantity"]))
            window_end = datetime.fromisoformat(record["window_end"]).replace(tzinfo=timezone.utc)
            STAT_WINDOW_END.labels(symbol).set(window_end.timestamp())
    finally:
        consumer.close()


def produce(args: argparse.Namespace) -> None:
    config = {"bootstrap.servers": BOOTSTRAP_SERVERS, "client.id": "mock-exchange"}
    wait_for_broker(config)
    producer = Producer(config)
    prices = dict(REFERENCE_PRICES)
    delay = 1.0 / args.rate
    sent = 0
    metrics_stop = threading.Event()
    start_http_server(METRICS_PORT)
    metrics_thread = threading.Thread(target=export_statistics, args=(metrics_stop,), daemon=True)
    metrics_thread.start()

    print(f"Publishing mock trades to {INPUT_TOPIC}; metrics available on :{METRICS_PORT}/metrics", flush=True)
    try:
        while args.count == 0 or sent < args.count:
            trade = build_trade(prices)
            payload = json.dumps(trade).encode("utf-8")
            while True:
                try:
                    producer.produce(INPUT_TOPIC, key=trade["symbol"], value=payload)
                    break
                except BufferError:
                    producer.poll(0.25)
            producer.poll(0)
            sent += 1
            print(json.dumps(trade), flush=True)
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        metrics_stop.set()
        metrics_thread.join(timeout=3)
        producer.flush(10)
        print(f"Published {sent} trade(s).", flush=True)


def consume(args: argparse.Namespace) -> None:
    config = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": f"statistics-viewer-{uuid.uuid4()}",
        "auto.offset.reset": "earliest" if args.from_beginning else "latest",
    }
    wait_for_broker({"bootstrap.servers": BOOTSTRAP_SERVERS})
    consumer = Consumer(config)
    consumer.subscribe([OUTPUT_TOPIC])
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"Reading Flink results from {OUTPUT_TOPIC}; press Ctrl+C to stop.", flush=True)
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() != KafkaError._PARTITION_EOF:
                    print(message.error(), file=sys.stderr, flush=True)
                continue
            record = json.loads(message.value().decode("utf-8"))
            print(json.dumps(record, indent=2), flush=True)
    finally:
        consumer.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock exchange Kafka client")
    commands = parser.add_subparsers(dest="command", required=True)

    producer_parser = commands.add_parser("produce", help="publish simulated trades")
    producer_parser.add_argument("--count", type=int, default=0, help="number of trades; 0 means forever")
    producer_parser.add_argument("--rate", type=float, default=5.0, help="trades per second")
    producer_parser.set_defaults(handler=produce)

    consumer_parser = commands.add_parser("consume", help="print Flink window results")
    consumer_parser.add_argument("--from-beginning", action="store_true")
    consumer_parser.set_defaults(handler=consume)

    args = parser.parse_args()
    if args.command == "produce" and args.rate <= 0:
        parser.error("--rate must be greater than zero")
    if args.command == "produce" and args.count < 0:
        parser.error("--count cannot be negative")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    parsed.handler(parsed)
