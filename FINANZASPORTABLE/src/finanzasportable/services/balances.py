from __future__ import annotations
from .db import connect

def listar_saldos_por_cuenta(db_path):
    """
    Devuelve filas (id, name, currency, balance, metadata) por cuenta.
    Usa la vista v_balance_por_cuenta si existe; si no, calcula con SUM().
    """
    with connect(db_path) as con:
        # ¿Existe la vista?
        has_view = con.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='view' AND name='v_balance_por_cuenta'
        """).fetchone() is not None

        if has_view:
            sql = """
                SELECT a.id, a.name, a.currency,
                       COALESCE(v.balance, 0) AS balance,
                       a.metadata
                FROM account a
                LEFT JOIN v_balance_por_cuenta v
                  ON v.account_id = a.id
                ORDER BY a.name
            """
        else:
            sql = """
                SELECT a.id, a.name, a.currency,
                       COALESCE(SUM(t.amount), 0) AS balance,
                       a.metadata
                FROM account a
                LEFT JOIN transactions t
                  ON t.account_id = a.id
                GROUP BY a.id, a.name, a.currency, a.metadata
                ORDER BY a.name
            """
        return con.execute(sql).fetchall()

def total_saldo(db_path) -> float:
    """Suma global de todos los movimientos (puede ser 0 si no hay datos)."""
    with connect(db_path) as con:
        row = con.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions").fetchone()
        return float(row[0] or 0.0)
