from pyiceberg.catalog import load_catalog

# Initialize Catalog
catalog = load_catalog(
    "default",
    **{
        "type": "rest",
        "uri": "http://localhost:8181",
        "s3.endpoint": "http://localhost:9000",
        "s3.access-key-id": "minioadmin",
        "s3.secret-access-key": "minioadmin",
    }
)

# load Iceberg Table
try:
    table = catalog.load_table("default.events")
    df = table.scan().to_arrow()
    print("--- Iceberg Table ---")
    print(df)
except Exception as e:
    print(f"Error: {e}")

# get current snapshot and history
print(f"Current snapshot ID: {table.current_snapshot().snapshot_id if table.current_snapshot() else 'None'}")
print("historical snapshots:")
for snapshot in table.history():
    print(snapshot)

