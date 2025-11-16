from __future__ import annotations
from pathlib import Path
import sqlite3
from contextlib import contextmanager

# --- Carpeta de datos ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# --- Rutas de BD ---
def db_path_general() -> Path:
    return DATA_DIR / "general.db"

def db_path_year(year: int) -> Path:
    return DATA_DIR / f"{year}.db"

def db_path_month(year: int, month: int) -> Path:
    return DATA_DIR / f"{year}-{month:02d}.db"

# --- Conexión (context manager) ---
@contextmanager
def connect(path: Path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

# --- Esquema base ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS institution(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  alias TEXT
);
CREATE TABLE IF NOT EXISTS account(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institution_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'ARS',
  metadata TEXT,
  FOREIGN KEY(institution_id) REFERENCES institution(id)
);
CREATE TABLE IF NOT EXISTS category(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('IN','OUT')),
  UNIQUE(name,type)
);
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  category_id INTEGER,
  posted_at TEXT NOT NULL,         -- ISO YYYY-MM-DD
  description TEXT DEFAULT '',
  amount REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'ARS',
  deleted_at TEXT DEFAULT NULL,
  FOREIGN KEY(account_id) REFERENCES account(id),
  FOREIGN KEY(category_id) REFERENCES category(id)
);
CREATE VIEW IF NOT EXISTS v_balance_por_cuenta AS
SELECT a.id AS account_id, a.name AS account_name, a.currency,
       IFNULL(SUM(CASE WHEN t.deleted_at IS NULL THEN t.amount ELSE 0 END),0) AS balance
FROM account a
LEFT JOIN transactions t ON t.account_id = a.id
GROUP BY a.id,a.name,a.currency;
"""

def ensure_schema(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as con:
        con.executescript(SCHEMA)

def db_empty_of_core_tables(path: Path) -> bool:
    with connect(path) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return not {"institution", "account", "category"}.issubset(tables)

def clone_core_from_general(target: Path):
    """
    Si 'target' no tiene tablas core, clona institution/account/category desde la GENERAL.
    """
    src = db_path_general()
    if not src.exists():
        return
    ensure_schema(src)
    ensure_schema(target)
    with connect(src) as cg, connect(target) as ct:
        cur = ct.execute("SELECT COUNT(*) FROM account").fetchone()[0]
        if cur:
            return
        for t in ("institution", "account", "category"):
            rows = cg.execute("SELECT * FROM ?", (t,)).fetchall()
            if not rows:
                continue
            cols = [d[1] for d in cg.execute("PRAGMA table_info(?)", (t,)).fetchall()]
            cols_no_id = [c for c in cols if c != "id"]
            placeholders = ",".join("?" for _ in cols_no_id)
            collist = ",".join(cols_no_id)
            for r in rows:
                vals = [r[c] for c in cols_no_id]
                ct.execute("INSERT INTO ?(?) VALUES (?)", (t, collist, placeholders), vals)

# --- Sincronización segura del "core" (evita 'database ... is locked') ---
def sync_core_from_general(dst_path: Path):
    """
    Copia/sincroniza institution, account y category desde la BD GENERAL hacia dst_path.
    - Sin 'import' dentro de esta función (evita import circular).
    - Usa busy_timeout y WAL.
    - Adjunta y SIEMPRE desadjunta (DETACH) la base 'gen' en un finally.
    """
    ensure_schema(dst_path)
    gen_path = db_path_general()

    with connect(dst_path) as con:
        # tolerancia a bloqueos y journaling seguro
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA journal_mode=WAL")

        try:
            con.execute("ATTACH DATABASE ? AS gen", (str(gen_path),))

            # institutions
            con.execute("""
                INSERT OR IGNORE INTO institution(id, name, alias)
                SELECT id, name, alias FROM gen.institution;
            """)
            # accounts
            con.execute("""
                INSERT OR IGNORE INTO account(id, institution_id, name, type, currency, metadata)
                SELECT id, institution_id, name, type, currency, metadata FROM gen.account;
            """)
            # categories
            con.execute("""
                INSERT OR IGNORE INTO category(id, name, type)
                SELECT id, name, type FROM gen.category;
            """)

            con.commit()
        finally:
            # Detach garantizado (aunque haya saltado una excepción)
            try:
                con.execute("DETACH DATABASE gen")
            except sqlite3.OperationalError:
                pass
