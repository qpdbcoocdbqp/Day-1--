import pathway as pw
import time
import logging
import os


logging.basicConfig(level=logging.INFO)

class DemoStream(pw.io.python.ConnectorSubject):
    def run(self):
        counter = 0
        while True:
            # logging.info(f"Producing value: {counter}")
            self.next(value=counter)
            counter += 1
            time.sleep(1)

class InputSchema(pw.Schema):
    value: int

table = pw.io.python.read(DemoStream(), schema=InputSchema)
table = table.reduce(sum=pw.reducers.sum(pw.this.value))
pw.io.null.write(table)

logging.info("Starting Pathway ETL with internal monitoring dashboard...")
pw.run(monitoring_level=pw.MonitoringLevel.ALL)
