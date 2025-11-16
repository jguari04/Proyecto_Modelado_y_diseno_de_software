from __future__ import annotations
from pathlib import Path
import sqlite3
from .db import connect, ensure_schema, db_path_general

def ensure_core_cloned(dst_path: Path) -> None:
    """
    Garantiza que la BD 'dst_path' tenga institution/account/category copiadas
    desde la BD general. Usa INSERT OR IGNORE para evitar duplicados.
    Seguro contra 'database is locked' y siempre DETACH al final.
    """
    ensure_schema(dst_path)  # por si es una base nueva

    gen_path = db_path_general()
    with connect(dst_path) as con:
        # Evitar bloqueos y mejorar concurrencia
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA journal_mode=WAL")

        # Si ya hay filas en account, asumimos que el core existe y no clonamos de nuevo
        row = con.execute("SELECT COUNT(*) FROM account").fetchone()
        if row and int(row[0]) > 0:
            return

        try:
            con.execute("ATTACH DATABASE ? AS gen", (str(gen_path),))

            # Copiar instituciones
            con.execute("""
                INSERT OR IGNORE INTO institution(id, name, alias)
                SELECT id, name, alias FROM gen.institution;
            """)

            # Copiar cuentas
            con.execute("""
                INSERT OR IGNORE INTO account(id, institution_id, name, type, currency, metadata)
                SELECT id, institution_id, name, type, currency, metadata
                FROM gen.account;
            """)

            # Copiar categorías
            con.execute("""
                INSERT OR IGNORE INTO category(id, name, type)
                SELECT id, name, type FROM gen.category;
            """)

            con.commit()
        finally:
            try:
                con.execute("DETACH DATABASE gen")
            except sqlite3.OperationalError:
                pass
