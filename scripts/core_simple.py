from pathlib import Path
import sys
from finanzasportable.services.db import connect, db_path_general
try:
    # si existe, la usamos para clonar a cada base
    from finanzasportable.services.core_sync import ensure_core_cloned
except Exception:
    ensure_core_cloned = None

ROOT  = Path(__file__).resolve().parents[1]
DBDIR = ROOT / "data"

# ---------- helpers ----------
def add_account(name, currency="ARS", acc_type="wallet"):
    db = db_path_general()
    with connect(db) as con:
        con.execute(
            "INSERT OR IGNORE INTO account(name, currency, type) VALUES (?,?,?)",
            (name.strip(), currency.strip(), acc_type.strip())
        )
    print(f"✔ Cuenta '{name}' en GENERAL.")

def rename_account(old_name, new_name):
    db = db_path_general()
    with connect(db) as con:
        con.execute("UPDATE account SET name=? WHERE name=?", (new_name.strip(), old_name.strip()))
    print(f"✔ Cuenta renombrada: '{old_name}' → '{new_name}'.")

def delete_account(name):
    db = db_path_general()
    with connect(db) as con:
        con.execute("DELETE FROM account WHERE name=?", (name.strip(),))
    print(f"✔ Cuenta eliminada: '{name}' en GENERAL.")

def add_category(name):
    db = db_path_general()
    with connect(db) as con:
        con.execute("INSERT OR IGNORE INTO category(name) VALUES(?)", (name.strip(),))
    print(f"✔ Categoría '{name}' en GENERAL.")

def rename_category(old_name, new_name):
    db = db_path_general()
    with connect(db) as con:
        con.execute("UPDATE category SET name=? WHERE name=?", (new_name.strip(), old_name.strip()))
    print(f"✔ Categoría renombrada: '{old_name}' → '{new_name}'.")

def delete_category(name):
    db = db_path_general()
    with connect(db) as con:
        con.execute("DELETE FROM category WHERE name=?", (name.strip(),))
    print(f"✔ Categoría eliminada: '{name}' en GENERAL.")

def sync_all():
    if ensure_core_cloned is None:
        print("ⓘ No encontré ensure_core_cloned; abrí la app y cambiá de mes para que sincronice.")
        return
    g = db_path_general()
    count = 0
    for p in sorted(DBDIR.glob("*.db")):
        if p.name.lower() == Path(g).name.lower():
            continue
        ensure_core_cloned(p)
        count += 1
    print(f"✔ Core sincronizado a {count} bases (mes/año).")

def list_all(where="general"):
    if where == "general":
        db = db_path_general()
    else:
        # where = "YYYY-##" o "YYYY"
        if "-" in where:
            y, m = where.split("-", 1)
            db = DBDIR / f"{int(y):04d}-{int(m):02d}.db"
        else:
            db = DBDIR / f"{int(where):04d}.db"
    with connect(db) as con:
        print(f"\n== Cuentas en {db} ==")
        for r in con.execute("SELECT name, currency, type FROM account ORDER BY name"):
            print(f" - {r['name']} ({r['currency']}) [{r['type']}]")
        print(f"\n== Categorías en {db} ==")
        for r in con.execute("SELECT name FROM category ORDER BY name"):
            print(f" - {r['name']}")

# ---------- CLI ----------
USAGE = """
Uso:

  # Cuentas
  python scripts/core_simple.py add-account "Nombre" [ARS] [wallet|checking|cash]
  python scripts/core_simple.py rename-account "Viejo" "Nuevo"
  python scripts/core_simple.py del-account "Nombre"

  # Categorías
  python scripts/core_simple.py add-category "Nombre"
  python scripts/core_simple.py rename-category "Viejo" "Nuevo"
  python scripts/core_simple.py del-category "Nombre"

  # Sincronizar a todos los meses/años
  python scripts/core_simple.py sync

  # Listar (para ver que esté todo)
  python scripts/core_simple.py list               # lista GENERAL
  python scripts/core_simple.py list 2025          # lista 2025.db
  python scripts/core_simple.py list 2025-11       # lista 2025-11.db
"""

def main():
    if len(sys.argv) < 2:
        print(USAGE); return
    cmd = sys.argv[1]

    if cmd == "add-account":
        name = sys.argv[2]
        currency = sys.argv[3] if len(sys.argv) > 3 else "ARS"
        acc_type = sys.argv[4] if len(sys.argv) > 4 else "wallet"
        add_account(name, currency, acc_type)

    elif cmd == "rename-account":
        rename_account(sys.argv[2], sys.argv[3])

    elif cmd == "del-account":
        delete_account(sys.argv[2])

    elif cmd == "add-category":
        add_category(sys.argv[2])

    elif cmd == "rename-category":
        rename_category(sys.argv[2], sys.argv[3])

    elif cmd == "del-category":
        delete_category(sys.argv[2])

    elif cmd == "sync":
        sync_all()

    elif cmd == "list":
        where = sys.argv[2] if len(sys.argv) > 2 else "general"
        list_all(where)

    else:
        print(USAGE)

if __name__ == "__main__":
    main()
