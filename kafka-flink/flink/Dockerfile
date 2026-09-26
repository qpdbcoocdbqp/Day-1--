ARG FLINK_VERSION=1.20.1
ARG KAFKA_CONNECTOR_VERSION=3.4.0-1.20

FROM curlimages/curl:8.10.1 AS connector
ARG KAFKA_CONNECTOR_VERSION
RUN curl --fail --location --show-error \
    "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VERSION}/flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar" \
    --output /tmp/flink-sql-connector-kafka.jar

FROM flink:${FLINK_VERSION}-scala_2.12-java17
COPY --from=connector /tmp/flink-sql-connector-kafka.jar /opt/flink/lib/flink-sql-connector-kafka.jar
RUN curl --fail --location --show-error \
    "https://repo.maven.apache.org/maven2/org/apache/flink/flink-metrics-prometheus/1.20.1/flink-metrics-prometheus-1.20.1.jar" \
    --output /opt/flink/lib/flink-metrics-prometheus.jar
