from __future__ import annotations
from .db import connect

def listar_transacciones(db_path):
    """Devuelve las últimas 500 transacciones con nombre de cuenta."""
    with connect(db_path) as con:
        return con.execute("""
            SELECT t.id,
                   t.posted_at,
                   t.description,
                   t.amount,
                   a.name AS account_name
            FROM transactions t
            JOIN account a ON a.id = t.account_id
            ORDER BY t.posted_at DESC, t.id DESC
            LIMIT 500
        """).fetchall()
