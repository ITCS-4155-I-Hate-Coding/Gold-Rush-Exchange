# run: python apply_schema.py
# creates or updates every table in schema.sql (safe to run again, everything is IF NOT EXISTS)

from pathlib import Path

from db import transaction

sql = (Path(__file__).resolve().parent / "schema.sql").read_text()

# one transaction: if any statement fails, nothing is changed
with transaction() as tx:
    tx.query(sql, fetch=False)

print("schema is up to date")
