-- Runs on the first start of an empty ClickHouse volume.
-- The Kafka engine table reads exchange.symbol-statistics, and the materialized view copies each batch
-- into exchange_symbol_statistics. The Kafka engine is at-least-once, so ReplacingMergeTree collapses
-- redelivered windows on (symbol, window_start); query with FINAL to see the deduplicated rows.

CREATE TABLE IF NOT EXISTS exchange_symbol_statistics
(
    symbol LowCardinality(String),
    window_start DateTime64(3, 'UTC'),
    window_end DateTime64(3, 'UTC'),
    trade_count UInt64,
    total_quantity Decimal(38, 6),
    low_price Decimal(18, 4),
    high_price Decimal(18, 4),
    average_price Decimal(18, 4),
    buy_quantity Decimal(38, 6),
    sell_quantity Decimal(38, 6)
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMMDD(window_start)
ORDER BY (symbol, window_start);

CREATE TABLE IF NOT EXISTS exchange_symbol_statistics_queue
(
    symbol String,
    window_start DateTime64(3, 'UTC'),
    window_end DateTime64(3, 'UTC'),
    trade_count UInt64,
    total_quantity Decimal(38, 6),
    low_price Decimal(18, 4),
    high_price Decimal(18, 4),
    average_price Decimal(18, 4),
    buy_quantity Decimal(38, 6),
    sell_quantity Decimal(38, 6)
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'exchange.symbol-statistics',
    kafka_group_name = 'clickhouse-symbol-statistics',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS exchange_symbol_statistics_mv
TO exchange_symbol_statistics
AS SELECT * FROM exchange_symbol_statistics_queue;
