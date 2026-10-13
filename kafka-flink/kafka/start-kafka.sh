#!/bin/sh
set -eu

# Create the topics in the background once the broker answers, then run Kafka in the foreground.
(
  until /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do
    sleep 2
  done
  for topic in exchange.trades exchange.symbol-statistics; do
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
      --create --if-not-exists --topic "$topic" --partitions 3 --replication-factor 1
  done
) &

exec /__cacert_entrypoint.sh /etc/kafka/docker/run
