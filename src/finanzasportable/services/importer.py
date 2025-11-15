from __future__ import annotations
from pathlib import Path
import pandas as pd
from typing import Dict, Tuple
from ..services.db import connect
from ..utils.formats import parse_amount

def read_any_table(path: Path, sheet: str | None = None, header_row: int = 0) -> pd.DataFrame:
    if str(path).lower().endswith((".xlsx",".xls")):
        return pd.read_excel(path, sheet_name=sheet or 0, header=header_row)
    return pd.read_csv(path, header=header_row)

def guess_role(colname: str) -> str | None:
    c = colname.lower()
    if any(k in c for k in ("fecha","date","posted")): return "date"
    if any(k in c for k in ("cuenta","account")): return "account"
    if any(k in c for k in ("desc","concept","detalle","memo")): return "description"
    if any(k in c for k in ("monto","amount","importe")): return "amount"
    if any(k in c for k in ("moneda","currency")): return "currency"
    return None

def normalize_with_mapping(df, mapping: Dict[str,str|None], defaults: Dict[str,str]) -> pd.DataFrame:
    out = pd.DataFrame()
    # Fecha
    col_date = mapping.get("date")
    out["posted_at"] = pd.to_datetime(df[col_date], errors="coerce").dt.date.astype(str) if col_date else ""
    # Cuenta
    col_acc = mapping.get("account")
    out["account"] = df[col_acc].astype(str) if col_acc else defaults.get("account","General")
    # Descripción
    col_desc = mapping.get("description")
    out["description"] = df[col_desc].astype(str) if col_desc else ""
    # Monto
    col_amt = mapping.get("amount")
    if col_amt:
        out["amount"] = df[col_amt].apply(lambda x: parse_amount(str(x)))
    else:
        out["amount"] = 0.0
    # Moneda
    col_curr = mapping.get("currency")
    out["currency"] = (df[col_curr].astype(str) if col_curr else defaults.get("currency","ARS"))
    # Limpieza
    out = out.dropna(subset=["posted_at"])
    return out

def import_rows(conn, df) -> Tuple[int,int]:
    """Crea cuentas faltantes por 'name' y carga transacciones."""
    cur = conn.cursor()
    # Map account name -> id (y crear si no existe, asignando institution 1 o nula)
    acc_map = {}
    for acc_name in df["account"].dropna().unique():
        r = cur.execute("SELECT id FROM account WHERE name=?", (acc_name,)).fetchone()
        if r: acc_map[acc_name] = r[0]
        else:
            inst = cur.execute("SELECT id FROM institution ORDER BY id LIMIT 1").fetchone()
            inst_id = inst[0] if inst else 1
            cur.execute("INSERT OR IGNORE INTO institution(id,name) VALUES (?,?)", (inst_id, "Genérica") )
            cur.execute("INSERT INTO account(institution_id,name,type,currency,metadata) VALUES (?,?,?,?,?)",
                        (inst_id, acc_name, "wallet", "ARS", '{"position": 999999999}'))
            acc_map[acc_name] = cur.lastrowid
    inserted = 0
    for _,row in df.iterrows():
        aid = acc_map.get(row["account"])
        cur.execute(
            "INSERT INTO transactions(account_id, posted_at, description, amount, currency) VALUES (?,?,?,?,?)",
            (aid, row["posted_at"], row.get("description","") or "", float(row["amount"]), row.get("currency","ARS"))
        )
        inserted += 1
    return (len(acc_map), inserted)
