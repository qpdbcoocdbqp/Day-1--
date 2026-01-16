import logging
import time

import pathway as pw

logging.basicConfig(level=logging.INFO)

pw.set_license_key(key="***")
pw.set_monitoring_config(
    server_endpoint=None,#"http://localhost:4317", 
    detailed_metrics_dir="./monitoring/metrics"
    )


class DemoStream(pw.io.python.ConnectorSubject):
    def run(self):
        while True:
            logging.info("Producing value")
            self.next(value=1)
            time.sleep(1)

class InputSchema(pw.Schema):
    value: int

table = pw.io.python.read(DemoStream(), schema=InputSchema)
table = table.reduce(sum=pw.reducers.sum(pw.this.value))
pw.io.null.write(table)

pw.run()
