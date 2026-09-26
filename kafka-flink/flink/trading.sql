SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '10 s';
SET 'table.exec.source.idle-timeout' = '5 s';
SET 'pipeline.name' = 'exchange-symbol-statistics';

CREATE TABLE exchange_trades (
  trade_id STRING,
  symbol STRING,
  side STRING,
  price DECIMAL(18, 4),
  quantity DECIMAL(18, 6),
  event_time TIMESTAMP(3),
  WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'exchange.trades',
  'properties.bootstrap.servers' = 'kafka:9092',
  'properties.group.id' = 'flink-exchange-analytics',
  'properties.auto.offset.reset' = 'earliest',
  'scan.startup.mode' = 'group-offsets',
  'format' = 'json',
  'json.fail-on-missing-field' = 'false',
  'json.ignore-parse-errors' = 'false'
);

CREATE TABLE symbol_statistics (
  symbol STRING,
  window_start TIMESTAMP(3),
  window_end TIMESTAMP(3),
  trade_count BIGINT,
  total_quantity DECIMAL(38, 6),
  low_price DECIMAL(18, 4),
  high_price DECIMAL(18, 4),
  average_price DECIMAL(18, 4),
  buy_quantity DECIMAL(38, 6),
  sell_quantity DECIMAL(38, 6)
) WITH (
  'connector' = 'kafka',
  'topic' = 'exchange.symbol-statistics',
  'properties.bootstrap.servers' = 'kafka:9092',
  'properties.transaction.timeout.ms' = '600000',
  'sink.delivery-guarantee' = 'exactly-once',
  'sink.transactional-id-prefix' = 'flink-exchange-analytics-',
  'format' = 'json'
);

INSERT INTO symbol_statistics
SELECT
  symbol,
  window_start,
  window_end,
  COUNT(*) AS trade_count,
  SUM(quantity) AS total_quantity,
  MIN(price) AS low_price,
  MAX(price) AS high_price,
  CAST(AVG(price) AS DECIMAL(18, 4)) AS average_price,
  SUM(CASE WHEN side = 'BUY' THEN quantity ELSE CAST(0 AS DECIMAL(18, 6)) END) AS buy_quantity,
  SUM(CASE WHEN side = 'SELL' THEN quantity ELSE CAST(0 AS DECIMAL(18, 6)) END) AS sell_quantity
FROM TABLE(
  TUMBLE(TABLE exchange_trades, DESCRIPTOR(event_time), INTERVAL '10' SECOND)
)
GROUP BY symbol, window_start, window_end;
