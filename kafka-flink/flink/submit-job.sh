#!/usr/bin/env bash
set -euo pipefail

echo "Submitting the exchange analytics SQL job to Flink..."

if /opt/flink/bin/flink list -r 2>/dev/null | grep -Fq "exchange-symbol-statistics"; then
  echo "The exchange analytics job is already running; skipping submission."
  exit 0
fi

exec /opt/flink/bin/sql-client.sh -f /opt/flink/usrlib/trading.sql
