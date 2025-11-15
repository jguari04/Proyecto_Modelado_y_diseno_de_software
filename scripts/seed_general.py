# Hace que el paquete "finanzasportable" se pueda importar desde ./src
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finanzasportable.services.db import connect, ensure_schema, db_path_general

p = db_path_general()
ensure_schema(p)

with connect(p) as con:
    # Crea la institución por defecto si no existe
    con.execute("INSERT OR IGNORE INTO institution(name,alias) VALUES (?,?)", ("Genérica","GEN"))
    inst_id = con.execute("SELECT id FROM institution WHERE name=?", ("Genérica",)).fetchone()[0]

    # Crea la cuenta "General" si no existe
    con.execute("""
        INSERT OR IGNORE INTO account(institution_id,name,type,currency,metadata)
        VALUES (?,?,?,?,?)
    """, (inst_id, "General", "wallet", "ARS", '{"position": 1}'))

    # Crea categorías básicas si no existen (opcional)
    con.execute("INSERT OR IGNORE INTO category(name,type) VALUES ('Sueldo','IN'), ('Comida','OUT')")

print("OK. Semilla creada en:", p)
