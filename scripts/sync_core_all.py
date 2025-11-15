from pathlib import Path
from manage_core_gui import ensure_schema, ensure_core_cloned, db_path_general, DBDIR

# Asegura GENERAL y copia core a todos los .db (menos GENERAL)
g = ensure_schema(db_path_general())
count = 0
for p in sorted(DBDIR.glob("*.db")):
    if p.name == "general.db": 
        continue
    ensure_schema(p)
    ensure_core_cloned(p)
    count += 1
print(f"✅ Core de GENERAL replicado a {count} bases.")
