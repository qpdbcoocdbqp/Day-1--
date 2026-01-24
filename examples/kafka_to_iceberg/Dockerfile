FROM pathwaycom/pathway:latest

WORKDIR /app

# Copy the pipeline code
COPY kafka_to_iceberg.py .

# Set environment variables (can be overridden at runtime)
ENV KAFKA_BOOTSTRAP_SERVERS=redpanda:29092
ENV ICEBERG_CATALOG_URI=http://iceberg-rest:8181

# Run the pipeline
CMD ["python", "kafka_to_iceberg.py"]
