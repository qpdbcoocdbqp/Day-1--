#!/usr/bin/env bash
set -euo pipefail

# Submit the SQL job in the background once the REST endpoint is up, then run the JobManager in the foreground.
(
  until curl --fail --silent http://localhost:8081/overview >/dev/null 2>&1; do
    sleep 2
  done

  echo "Submitting the exchange analytics SQL job to Flink..."
  if /opt/flink/bin/flink list -r 2>/dev/null | grep -Fq "exchange-symbol-statistics"; then
    echo "The exchange analytics job is already running; skipping submission."
  else
    /opt/flink/bin/sql-client.sh -f /opt/flink/usrlib/trading.sql || echo "Job submission failed; restart the jobmanager to retry."
  fi
) &

exec /docker-entrypoint.sh jobmanager
