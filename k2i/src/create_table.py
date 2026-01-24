from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, IntegerType, StringType, DoubleType


# initialize Iceberg Catalog
catalog = load_catalog(
    "default",
    **{
        "type": "rest",
        "uri": "http://localhost:8181",
        "s3.endpoint": "http://localhost:9000",
        "s3.access-key-id": "minioadmin",
        "s3.secret-access-key": "minioadmin",
        "s3.path-style-access": "true"
    }
)

# create namespace
try:
    catalog.create_namespace("default")
    print("✅ Namespace 'default' successfully created")
except Exception as e:
    print(f"ℹ️ Namespace may existed: {e}")

# create table
schema = Schema(
    NestedField(field_id=1, name="event_id", field_type=IntegerType(), required=False),
    NestedField(field_id=2, name="user_id", field_type=IntegerType(), required=False),
    NestedField(field_id=3, name="event_type", field_type=StringType(), required=False),
    NestedField(field_id=4, name="timestamp", field_type=DoubleType(), required=False),
    NestedField(field_id=5, name="value", field_type=DoubleType(), required=False)
)

table_name = "default.events"
if table_name not in [t[1] for t in catalog.list_tables("default")]:
    catalog.create_table(table_name, schema=schema)
    print(f"✅ Successfully created Iceberg table: {table_name}")
else:
    print(f"ℹ️ Table {table_name} existed")