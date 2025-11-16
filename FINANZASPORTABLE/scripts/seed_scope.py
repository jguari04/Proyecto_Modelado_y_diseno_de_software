from finanzasportable.services.db import ensure_schema, db_path_year, db_path_month, connect, clone_core_from_general, db_empty_of_core_tables
from datetime import date
y = date.today().year
ensure_schema(db_path_year(y))
if db_empty_of_core_tables(db_path_year(y)):
    clone_core_from_general(db_path_year(y))
ensure_schema(db_path_month(y, date.today().month))
if db_empty_of_core_tables(db_path_month(y, date.today().month)):
    clone_core_from_general(db_path_month(y, date.today().month))
print("Seeds OK.")
