#!/bin/sh
set -u

# Submit the Kafka supervisor in the background once the router is healthy, then run the router in the foreground.
(
  until wget -qO- http://localhost:8888/status/health 2>/dev/null | grep -q true; do
    sleep 3
  done
  until wget -qO- --header='Content-Type: application/json' \
      --post-file=/spec/supervisor-spec.json \
      http://localhost:8888/druid/indexer/v1/supervisor >/dev/null 2>&1; do
    sleep 5
  done
  echo "Druid supervisor submitted."
) &

exec /druid.sh router
