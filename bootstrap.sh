#!/usr/bin/env bash
set -euo pipefail

# === 0) Proyecto base ===
PROJECT="FINANZASPORTABLE"
mkdir -p "$PROJECT"
cd "$PROJECT"

echo "▶ Creando estructura..."
mkdir -p src/finanzasportable/{services,utils}
mkdir -p app data scripts docs tests diagnostics

# === 1) Entorno y dependencias ===
echo "▶ Creando .venv y requirements..."
python3 -m venv .venv
source .venv/bin/activate
cat > requirements.txt <<'REQ'
ttkbootstrap
pandas
openpyxl
REQ
pip install -q -r requirements.txt

# === 2) Utils: formatos (parseo y money) ===
cat > src/finanzasportable/utils/formats.py <<'PY'
from decimal import Decimal, InvalidOperation
import re

def parse_amount(s: str) -> float:
    """
    Acepta: "5.000,00" | "1,234.56" | "-1.200,50" | "$ 1.234,56" | "5000"
    Regresa float con signo correcto.
    """
    if s is None: raise ValueError("Monto vacío")
    s = str(s).strip()
    if not s: raise ValueError("Monto vacío")
    s = s.replace("$", "").replace("ARS", "").replace("USD", "").strip()
    # Detectar notación:
    if re.search(r",\d{2}$", s) and "." in s:
        # Formato ES: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",")==1 and s.count(".")==0:
        # Formato ES sin miles: 1234,56
        s = s.replace(",", ".")
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Monto inválido: {s}")

def money(x: float, currency: str = "ARS") -> str:
    sign = "-" if (x is not None and x < 0) else ""
    v = abs(x or 0.0)
    return f"{sign}{currency} {v:,.2f}".replace(",", "_").replace(".", ",").replace("_",".")
PY

# === 3) Servicios de BD: rutas, conexión, schema, clone core ===
cat > src/finanzasportable/services/db.py <<'PY'
from __future__ import annotations
from pathlib import Path
import sqlite3
from contextlib import contextmanager

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def db_path_general() -> Path:
    return DATA_DIR / "general.db"

def db_path_year(year: int) -> Path:
    return DATA_DIR / f"{year}.db"

def db_path_month(year: int, month: int) -> Path:
    return DATA_DIR / f"{year}-{month:02d}.db"

@contextmanager
def connect(path: Path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

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
    return not {"institution","account","category"}.issubset(tables)

def clone_core_from_general(target: Path):
    """Clona institution/account/category desde la base general si target está vacío."""
    src = db_path_general()
    if not src.exists(): return
    ensure_schema(src); ensure_schema(target)
    with connect(src) as cg, connect(target) as ct:
        # Si ya hay core en target, no hacer nada
        cur = ct.execute("SELECT COUNT(*) FROM account").fetchone()[0]
        if cur: return
        for t in ("institution","account","category"):
            rows = cg.execute(f"SELECT * FROM {t}").fetchall()
            if not rows: continue
            cols = [d[1] for d in cg.execute(f"PRAGMA table_info({t})").fetchall()]
            cols_no_id = [c for c in cols if c != "id"]
            placeholders = ",".join("?" for _ in cols_no_id)
            collist = ",".join(cols_no_id)
            for r in rows:
                vals = [r[c] for c in cols_no_id]
                ct.execute(f"INSERT INTO {t}({collist}) VALUES ({placeholders})", vals)
PY

# === 4) Importador sencillo (CSV/Excel con mapeo) ===
cat > src/finanzasportable/services/importer.py <<'PY'
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
PY

# === 5) GUI con correcciones (path robusto, COALESCE, bindings) ===
cat > app/gui_mp.py <<'PY'
# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from pathlib import Path
from datetime import date, datetime
import json
import sys as _sys

# --- asegurar import de paquete (buscar carpeta src hacia arriba) ---
def _ensure_src_in_syspath():
    p = Path(__file__).resolve()
    for anc in [p] + list(p.parents):
        src = anc / "src"
        if src.is_dir():
            s = str(src)
            if s not in _sys.path:
                _sys.path.insert(0, s)
            return
_ensure_src_in_syspath()

from finanzasportable.services.db import (
    connect, ensure_schema, clone_core_from_general, db_empty_of_core_tables,
    db_path_general, db_path_year, db_path_month
)
from finanzasportable.utils.formats import parse_amount, money
from finanzasportable.services.importer import read_any_table, guess_role, normalize_with_mapping, import_rows

def build_section(parent: tk.Misc, title: str):
    wrap = ttk.Frame(parent, padding=(8, 6, 8, 8))
    head = ttk.Frame(wrap); head.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(head, text=title, font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)
    ttk.Separator(wrap).pack(fill=tk.X)
    body = ttk.Frame(wrap); body.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
    return wrap, body

def _json_or_empty(s: str | None) -> dict:
    import json
    if not s: return {}
    try: return json.loads(s)
    except Exception: return {}

def _meta_with_position(s: str | None, pos: int) -> str:
    d = _json_or_empty(s); d["position"] = int(pos)
    return json.dumps(d, ensure_ascii=False)

def _position_from_meta(s: str | None) -> int:
    d = _json_or_empty(s)
    try: return int(d.get("position", 10**9))
    except Exception: return 10**9

class ImportWizard(tk.Toplevel):
    def __init__(self, master: tk.Misc, conn, default_account: str = "General"):
        super().__init__(master)
        self.conn = conn
        self.title("Importar CSV/Excel"); self.geometry("760x560"); self.resizable(True, True)
        self.path_var = tk.StringVar(); self.sheet_var = tk.StringVar(value=""); self.header_var = tk.IntVar(value=0)
        self.default_account = tk.StringVar(value=default_account)
        self.df = None; self.columns = []
        frm = ttk.Frame(self, padding=12); frm.pack(fill="both", expand=True)
        r1 = ttk.Frame(frm); r1.pack(fill="x", pady=4)
        ttk.Label(r1, text="Archivo (.csv / .xlsx)").pack(side="left")
        ttk.Entry(r1, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r1, text="Buscar…", command=self.browse).pack(side="left")
        r2 = ttk.Frame(frm); r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="Hoja (Excel)").pack(side="left")
        self.sheet_cb = ttk.Combobox(r2, textvariable=self.sheet_var, width=28, state="readonly"); self.sheet_cb.pack(side="left", padx=6)
        ttk.Label(r2, text="Fila encabezado").pack(side="left")
        ttk.Spinbox(r2, from_=0, to=100, textvariable=self.header_var, width=6).pack(side="left", padx=6)
        ttk.Button(r2, text="Previsualizar", command=self.preview).pack(side="left", padx=6)
        mapf = ttk.LabelFrame(frm, text="Mapeo de columnas"); mapf.pack(fill="x", pady=8)
        self.cmb = {}
        for r in ["date","account","description","amount","currency"]:
            fr = ttk.Frame(mapf); fr.pack(fill="x", pady=2)
            ttk.Label(fr, text=r.capitalize(), width=14).pack(side="left")
            cb = ttk.Combobox(fr, width=42, state="readonly"); cb.pack(side="left", fill="x", expand=True); self.cmb[r]=cb
        dfr = ttk.Frame(mapf); dfr.pack(fill="x", pady=2)
        ttk.Label(dfr, text="Cuenta por defecto", width=14).pack(side="left")
        ttk.Entry(dfr, textvariable=self.default_account).pack(side="left", fill="x", expand=True)
        self.preview_box = tk.Text(frm, height=14); self.preview_box.pack(fill="both", expand=True, pady=(6,6))
        br = ttk.Frame(frm); br.pack(fill="x")
        ttk.Button(br, text="Cancelar", bootstyle=SECONDARY, command=self.destroy).pack(side="right", padx=6)
        ttk.Button(br, text="Importar", bootstyle=PRIMARY, command=self.do_import).pack(side="right")
    def browse(self):
        p = filedialog.askopenfilename(title="Elegir archivo", filetypes=[("CSV/Excel","*.csv *.xlsx *.xls"),("Todos","*.*")])
        if not p: return
        self.path_var.set(p)
        if p.lower().endswith((".xlsx",".xls")):
            try:
                import pandas as pd
                xls = pd.ExcelFile(p); self.sheet_cb["values"]=xls.sheet_names
                if xls.sheet_names: self.sheet_var.set(xls.sheet_names[0])
            except Exception:
                self.sheet_cb["values"]=[]; self.sheet_var.set("")
    def preview(self):
        try:
            from pathlib import Path as P
            df = read_any_table(P(self.path_var.get()), sheet=self.sheet_var.get() or None, header_row=self.header_var.get())
        except Exception as e:
            messagebox.showerror("Error leyendo", str(e), parent=self); return
        self.df=df; self.columns=[str(c) for c in df.columns]
        for role, cb in self.cmb.items():
            guess=None
            for c in self.columns:
                if guess_role(c)==role: guess=c; break
            cb["values"]=self.columns; cb.set(guess or "")
        self.preview_box.delete("1.0","end"); self.preview_box.insert("end", df.head(30).to_string())
    def do_import(self):
        if self.df is None:
            messagebox.showwarning("Atención", "Previsualizá y mapeá columnas.", parent=self); return
        mapping = {role: self.cmb[role].get() or None for role in self.cmb}
        defaults = {"account": self.default_account.get().strip() or "General","currency":"ARS"}
        try:
            norm = normalize_with_mapping(self.df, mapping, defaults)
            n_acc, n_tx = import_rows(self.conn, norm)
            messagebox.showinfo("Importación", f"Cuentas detectadas/nuevas: {n_acc}\nMovimientos insertados: {n_tx}", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error importando", str(e), parent=self)

class MPApp(tb.Window):
    def __init__(self):
        super().__init__(title="Finanzas Portable — Estilo Mercado Pago", themename="darkly")
        self.geometry("1200x720")
        today=date.today()
        self.scope_mode=tk.StringVar(value="general"); self.scope_year=tk.IntVar(value=today.year); self.scope_month=tk.IntVar(value=today.month)
        self.db_path=db_path_general(); self.prepare_db()
        self._build_header(); self._build_body(); self._toggle_scope_widgets()
    def current_path(self)->Path:
        mode=self.scope_mode.get()
        if mode=="general": return db_path_general()
        elif mode=="year":  return db_path_year(self.scope_year.get())
        else:               return db_path_month(self.scope_year.get(), self.scope_month.get())
    def prepare_db(self):
        self.db_path=self.current_path(); ensure_schema(self.db_path)
        if db_empty_of_core_tables(self.db_path): clone_core_from_general(self.db_path)
    def _build_header(self):
        hdr=ttk.Frame(self,padding=10); hdr.pack(fill=tk.X)
        saldo_frame=ttk.Frame(hdr); saldo_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(saldo_frame,text="Disponible",font=("Helvetica",10,"bold")).pack(anchor="w")
        self.total_var=tk.StringVar(value="$ 0,00")
        ttk.Label(saldo_frame,textvariable=self.total_var,font=("Helvetica",26,"bold")).pack(anchor="w",pady=(2,0))
        actions=ttk.Frame(saldo_frame); actions.pack(anchor="w",pady=8)
        for txt in ("Ingresar","Transferir","Pagar","Invertir"):
            ttk.Button(actions,text=txt,bootstyle=SECONDARY).pack(side=tk.LEFT,padx=6)
        right=ttk.Frame(hdr); right.pack(side=tk.RIGHT)
        mrow=ttk.Frame(right); mrow.pack(anchor="e",pady=(0,6))
        ttk.Label(mrow,text="Ámbito de datos:").pack(side=tk.LEFT,padx=(0,6))
        cmb=ttk.Combobox(mrow,width=10,state="readonly",values=["General","Año","Mes"]); cmb.current(0); cmb.pack(side=tk.LEFT)
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._on_scope_change(cmb.get()))
        self.year_sp=ttk.Spinbox(mrow,from_=2000,to=2100,width=6,textvariable=self.scope_year)
        self.month_sp=ttk.Spinbox(mrow,from_=1,to=12,width=4,textvariable=self.scope_month)
        ttk.Label(mrow,text="Año").pack(side=tk.LEFT,padx=(8,2)); self.year_sp.pack(side=tk.LEFT)
        ttk.Label(mrow,text="Mes").pack(side=tk.LEFT,padx=(8,2)); self.month_sp.pack(side=tk.LEFT)
        # Refrescar al cambiar año/mes
        self.year_sp.configure(command=self._toggle_scope_widgets)
        self.month_sp.configure(command=self._toggle_scope_widgets)
        self.year_sp.bind("<FocusOut>", lambda e: self._toggle_scope_widgets())
        self.month_sp.bind("<FocusOut>", lambda e: self._toggle_scope_widgets())
        btns=ttk.Frame(right); btns.pack(anchor="e")
        ttk.Button(btns,text="Añadir",bootstyle=SUCCESS,command=self.open_add_modal).pack(side=tk.LEFT,padx=6)
        ttk.Button(btns,text="Actualizar",bootstyle=PRIMARY,command=self.refresh_all).pack(side=tk.LEFT,padx=6)
        ttk.Button(btns,text="Importar",bootstyle=INFO,command=self.on_import).pack(side=tk.LEFT,padx=6)
        ttk.Button(btns,text="Exportar",bootstyle=INFO,command=self.export_to_excel).pack(side=tk.LEFT,padx=6)
    def _on_scope_change(self, sel:str):
        self.scope_mode.set("general" if sel=="General" else "year" if sel=="Año" else "month")
        self._toggle_scope_widgets()
    def _toggle_scope_widgets(self):
        mode=self.scope_mode.get()
        self.year_sp.configure(state="normal" if mode in ("year","month") else "disabled")
        self.month_sp.configure(state="normal" if mode=="month" else "disabled")
        self.prepare_db(); self.refresh_all()
    def on_import(self):
        conn = connect(self.db_path)
        wiz = ImportWizard(self, conn, default_account="General")
        self.wait_window(wiz)
        try: conn.close()
        except Exception: pass
        self.refresh_all()
    def _build_body(self):
        body=ttk.Frame(self,padding=(10,0,10,10)); body.pack(fill=tk.BOTH, expand=True)
        left_wrap,left_body=build_section(body,"Saldos por cuenta"); left_wrap.pack(side=tk.LEFT, fill=tk.Y)
        left_top=ttk.Frame(left_body); left_top.pack(fill=tk.X, pady=(0,6))
        ttk.Button(left_top,text="Cuentas…",bootstyle=SECONDARY,command=self.open_accounts_manager).pack(side=tk.LEFT)
        left_canvas=tk.Canvas(left_body,borderwidth=0,highlightthickness=0)
        vsb=ttk.Scrollbar(left_body,orient="vertical",command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=vsb.set); vsb.pack(side=tk.RIGHT,fill=tk.Y); left_canvas.pack(side=tk.LEFT,fill=tk.Y)
        self.left_container=ttk.Frame(left_canvas)
        self.left_container.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.create_window((0,0), window=self.left_container, anchor="nw")
        center_wrap,center_body=build_section(body,"Tu última actividad"); center_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0))
        columns=("fecha","desc","tipo","monto","cuenta")
        self.tv=ttk.Treeview(center_body,columns=columns,show="headings",height=18)
        for key, title in zip(columns, ["Fecha","Descripción","Tipo","Monto","Cuenta"]): self.tv.heading(key,text=title)
        self.tv.column("fecha",width=110,anchor=tk.W); self.tv.column("desc",width=380,anchor=tk.W)
        self.tv.column("tipo",width=90,anchor=tk.CENTER); self.tv.column("monto",width=140,anchor=tk.E); self.tv.column("cuenta",width=180,anchor=tk.W)
        self.tv.pack(fill=tk.BOTH, expand=True)
        self.tv.tag_configure("ingreso",foreground="#31c48d"); self.tv.tag_configure("egreso",foreground="#e02424"); self.tv.tag_configure("neutro",foreground="#cbd5e1")
        tv_scroll=ttk.Scrollbar(center_body,orient="vertical",command=self.tv.yview); self.tv.configure(yscrollcommand=tv_scroll.set); tv_scroll.place(relx=1.0,rely=0,relheight=1.0,anchor="ne")
        self._tv_menu=tk.Menu(self.tv,tearoff=0); self._tv_menu.add_command(label="Eliminar movimiento",command=self.delete_selected_tx)
        self.tv.bind("<Button-3>", self._popup_tv)
    def _popup_tv(self,event):
        try:
            row_id=self.tv.identify_row(event.y)
            if row_id: self.tv.selection_set(row_id); self._tv_menu.tk_popup(event.x_root,event.y_root)
        finally:
            self._tv_menu.grab_release()
    def get_accounts(self)->list[dict]:
        with connect(self.db_path) as con:
            rows=con.execute("SELECT id, name, currency FROM account ORDER BY name").fetchall()
        return [{"id":r[0],"name":r[1],"currency":r[2]} for r in rows]
    def load_balances(self):
        for w in self.left_container.winfo_children(): w.destroy()
        total=0.0
        with connect(self.db_path) as con:
            rows = con.execute("""SELECT a.id, a.name, a.currency, COALESCE(v.balance,0) AS balance, a.metadata
                                  FROM account a LEFT JOIN v_balance_por_cuenta v ON v.account_id=a.id""").fetchall()
        rows = sorted(rows, key=lambda r: (_position_from_meta(r[4]), r[1].lower()))
        grp=ttk.Frame(self.left_container); grp.pack(anchor="w")
        for _acc_id, acc_name, curr, bal, _meta in rows:
            total += float(bal or 0)
            card=ttk.Frame(grp,padding=6,bootstyle=SECONDARY); card.pack(fill=tk.X, pady=4)
            ttk.Label(card,text=acc_name,font=("Helvetica",10,"bold"),bootstyle="inverse-secondary",anchor="w",padding=(4,1)).pack(fill="x")
            ttk.Label(card,text=curr,bootstyle="inverse-secondary",anchor="w",padding=(4,1)).pack(fill="x")
            ttk.Label(card,text=money(bal,curr),font=("Helvetica",12,"bold"),bootstyle="inverse-secondary",anchor="w",padding=(4,1)).pack(fill="x")
        self.total_var.set(money(total))
    def load_activity(self):
        for i in self.tv.get_children(): self.tv.delete(i)
        with connect(self.db_path) as con:
            rows = con.execute("""SELECT t.id,
                                         COALESCE(t.posted_at, t.date) AS posted_at,
                                         t.description, t.amount, a.name
                                  FROM transactions t
                                  JOIN account a ON a.id=t.account_id
                                  ORDER BY posted_at DESC, t.id DESC
                                  LIMIT 500""").fetchall()
        for tx_id, posted_at, desc, amount, acc_name in rows:
            tag = "ingreso" if amount>0 else "egreso" if amount<0 else "neutro"
            tipo= "Ingreso" if amount>0 else "Egreso" if amount<0 else "—"
            self.tv.insert("", "end", iid=str(tx_id),
                           values=(posted_at, desc or "", tipo, money(amount), acc_name),
                           tags=(tag,))
    def refresh_all(self):
        self.prepare_db(); self.load_balances(); self.load_activity()
    def open_accounts_manager(self):
        win = tb.Toplevel(self); win.title("Cuentas"); win.transient(self); win.grab_set(); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill=tk.BOTH,expand=True)
        accounts=self._fetch_accounts_with_meta(); lst=tk.Listbox(frm, height=14, activestyle="dotbox"); lst.grid(row=0,column=0,rowspan=7,sticky="nswe"); frm.columnconfigure(0,weight=1)
        def render_list():
            lst.delete(0,tk.END)
            for a in accounts: lst.insert(tk.END, f"{a['name']} ({a['currency']})")
        def cur_index():
            sel=lst.curselection(); return sel[0] if sel else None
        def move(delta:int):
            idx=cur_index(); 
            if idx is None: return
            new=max(0,min(len(accounts)-1, idx+delta))
            if new==idx: return
            accounts[idx],accounts[new]=accounts[new],accounts[idx]; render_list(); lst.selection_set(new)
        def rename():
            idx=cur_index(); 
            if idx is None: return
            a=accounts[idx]; new_name=simpledialog.askstring("Renombrar","Nuevo nombre:", initialvalue=a["name"], parent=win)
            if not new_name or not new_name.strip(): return
            new_name=new_name.strip()
            with connect(self.db_path) as con: con.execute("UPDATE account SET name=? WHERE id=?", (new_name, a["id"]))
            accounts[idx]["name"]=new_name; render_list(); lst.selection_set(idx); self.refresh_all()
        def new_account():
            self._open_new_account_modal(parent=win, on_created=lambda acc: (accounts.append(acc), render_list(), lst.selection_clear(0,tk.END), lst.selection_set(tk.END)))
        def delete_account():
            idx=cur_index(); 
            if idx is None: return
            a=accounts[idx]; others=[x for x in accounts if x["id"]!=a["id"]]
            self._open_delete_account_modal(parent=win, account=a, all_accounts=others, on_done=lambda: (accounts.pop(idx), render_list(), self.refresh_all()))
        def save_order():
            with connect(self.db_path) as con:
                for pos,a in enumerate(accounts, start=1):
                    meta=_meta_with_position(a.get("metadata"), pos)
                    con.execute("UPDATE account SET metadata=? WHERE id=?", (meta, a["id"]))
                    a["metadata"]=meta
            messagebox.showinfo("Cuentas","Orden guardado.", parent=win); self.refresh_all()
        btns=ttk.Frame(frm); btns.grid(row=0,column=1,sticky="n",padx=8)
        ttk.Button(btns,text="Nueva…",bootstyle=SUCCESS,command=new_account).pack(fill=tk.X,pady=2)
        ttk.Button(btns,text="Renombrar…",bootstyle=SECONDARY,command=rename).pack(fill=tk.X,pady=2)
        ttk.Button(btns,text="Eliminar…",bootstyle=DANGER,command=delete_account).pack(fill=tk.X,pady=2)
        ttk.Separator(btns).pack(fill=tk.X,pady=4)
        ttk.Button(btns,text="Subir ▲",command=lambda: move(-1)).pack(fill=tk.X,pady=2)
        ttk.Button(btns,text="Bajar ▼",command=lambda: move(+1)).pack(fill=tk.X,pady=2)
        ttk.Separator(btns).pack(fill=tk.X,pady=4)
        ttk.Button(btns,text="Guardar orden",bootstyle=PRIMARY,command=save_order).pack(fill=tk.X,pady=2)
        ttk.Button(btns,text="Cerrar",bootstyle=SECONDARY,command=win.destroy).pack(fill=tk.X,pady=8)
        render_list()
    def _fetch_accounts_with_meta(self)->list[dict]:
        with connect(self.db_path) as con:
            rows=con.execute("SELECT id, institution_id, name, type, currency, metadata FROM account").fetchall()
        accs=[{"id":r[0],"institution_id":r[1],"name":r[2],"type":r[3],"currency":r[4],"metadata":r[5]} for r in rows]
        accs.sort(key=lambda a: (_position_from_meta(a["metadata"]), a["name"].lower()))
        return accs
    def _open_new_account_modal(self, parent: tk.Misc, on_created):
        win=tb.Toplevel(parent); win.title("Nueva cuenta"); win.transient(parent); win.grab_set(); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill=tk.BOTH,expand=True)
        with connect(self.db_path) as con:
            inst_rows=con.execute("SELECT id, name FROM institution ORDER BY name").fetchall()
        if not inst_rows:
            ttk.Label(frm, text="No hay instituciones. Creá una en la base general.", foreground="#ff8080").grid(row=0,column=0,columnspan=2,sticky="w")
            ttk.Button(frm,text="Cerrar",command=win.destroy).grid(row=1,column=1,sticky="e",pady=8); return
        inst_labels=[r[1] for r in inst_rows]
        inst_var=tk.StringVar(value=inst_labels[0]); name_var=tk.StringVar(value=""); type_var=tk.StringVar(value="wallet"); curr_var=tk.StringVar(value="ARS")
        ttk.Label(frm,text="Institución").grid(row=0,column=0,sticky="w")
        ttk.Combobox(frm,values=inst_labels,state="readonly",textvariable=inst_var,width=32).grid(row=0,column=1,sticky="w",padx=6,pady=4)
        ttk.Label(frm,text="Nombre de cuenta").grid(row=1,column=0,sticky="w"); ttk.Entry(frm,textvariable=name_var,width=34).grid(row=1,column=1,sticky="w",padx=6,pady=4)
        ttk.Label(frm,text="Tipo").grid(row=2,column=0,sticky="w")
        ttk.Combobox(frm,values=["cash","wallet","checking","savings","brokerage","card"],state="readonly",textvariable=type_var,width=20).grid(row=2,column=1,sticky="w",padx=6,pady=4)
        ttk.Label(frm,text="Moneda").grid(row=3,column=0,sticky="w")
        ttk.Combobox(frm,values=["ARS","USD"],state="readonly",textvariable=curr_var,width=10).grid(row=3,column=1,sticky="w",padx=6,pady=4)
        bar=ttk.Frame(frm); bar.grid(row=4,column=0,columnspan=2,sticky="e",pady=(10,0))
        ttk.Button(bar,text="Cancelar",bootstyle=SECONDARY,command=win.destroy).pack(side=tk.RIGHT,padx=6)
        def crear():
            nombre=(name_var.get() or "").strip()
            if not nombre:
                messagebox.showwarning("Nueva cuenta","Ingresá un nombre.", parent=win); return
            inst_idx=inst_labels.index(inst_var.get()); inst_id=inst_rows[inst_idx][0]
            with connect(self.db_path) as con:
                cur=con.execute("INSERT INTO account(institution_id,name,type,currency,metadata) VALUES (?,?,?,?,?)",
                                (inst_id, nombre, type_var.get(), curr_var.get(), json.dumps({"position": 10**9})))
                new_id=cur.lastrowid
            win.destroy(); self.refresh_all()
            if on_created:
                on_created({"id":new_id,"institution_id":inst_id,"name":nombre,"type":type_var.get(),"currency":curr_var.get(),
                            "metadata":json.dumps({"position": 10**9})})
        ttk.Button(bar,text="Crear",bootstyle=SUCCESS,command=crear).pack(side=tk.RIGHT)
    def _open_delete_account_modal(self, parent: tk.Misc, account: dict, all_accounts: list[dict], on_done):
        with connect(self.db_path) as con:
            n_tx=con.execute("SELECT COUNT(*) FROM transactions WHERE account_id=?", (account["id"],)).fetchone()[0]
        win=tb.Toplevel(parent); win.title(f"Eliminar cuenta — {account['name']}"); win.transient(parent); win.grab_set(); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill=tk.BOTH,expand=True)
        msg = (f"La cuenta «{account['name']}» ({account['currency']}) tiene {n_tx} movimientos." if n_tx else f"La cuenta «{account['name']}» no tiene movimientos.")
        ttk.Label(frm,text=msg).grid(row=0,column=0,columnspan=2,sticky="w")
        target_var=tk.StringVar(value=all_accounts[0]["name"] if all_accounts else "")
        if n_tx and all_accounts:
            ttk.Label(frm,text="Mover movimientos a:").grid(row=1,column=0,sticky="w",pady=(8,0))
            opts=[f\"{a['name']} ({a['currency']})\" for a in all_accounts]
            cmb=ttk.Combobox(frm,values=opts,state="readonly",textvariable=target_var,width=32); cmb.grid(row=1,column=1,sticky="w",padx=6,pady=(8,0))
            if opts: cmb.current(0)
        bar=ttk.Frame(frm); bar.grid(row=2,column=0,columnspan=2,sticky="e",pady=(12,0))
        ttk.Button(bar,text="Cancelar",bootstyle=SECONDARY,command=win.destroy).pack(side=tk.RIGHT,padx=6)
        def eliminar_y_migrar():
            if not all_accounts:
                messagebox.showwarning("Eliminar","No hay otra cuenta destino para migrar.", parent=win); return
            sel=target_var.get()
            idx=next((i for i,a in enumerate(all_accounts) if sel.startswith(a["name"])),0)
            target_id=all_accounts[idx]["id"]
            if not messagebox.askyesno("Confirmar", f"¿Mover {n_tx} movimientos a «{all_accounts[idx]['name']}» y eliminar la cuenta?", parent=win): return
            with connect(self.db_path) as con:
                con.execute("UPDATE transactions SET account_id=? WHERE account_id=?", (target_id, account["id"]))
                con.execute("DELETE FROM account WHERE id=?", (account["id"],))
            win.destroy(); on_done()
        def eliminar_todo():
            if not messagebox.askyesno("Eliminar definitivamente","Esto eliminará la cuenta y TODOS sus movimientos. ¿Continuar?", parent=win): return
            with connect(self.db_path) as con:
                con.execute("DELETE FROM account WHERE id=?", (account["id"],))
            win.destroy(); on_done()
        if n_tx:
            ttk.Button(bar,text="Mover y eliminar",bootstyle=WARNING,command=eliminar_y_migrar).pack(side=tk.RIGHT,padx=6)
            ttk.Button(bar,text="Eliminar todo",bootstyle=DANGER,command=eliminar_todo).pack(side=tk.RIGHT,padx=6)
        else:
            ttk.Button(bar,text="Eliminar",bootstyle=DANGER,command=eliminar_todo).pack(side=tk.RIGHT,padx=6)
    def open_add_modal(self):
        win=tb.Toplevel(self); win.title("Añadir movimiento"); win.transient(self); win.grab_set(); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill=tk.BOTH,expand=True)
        accounts=self.get_accounts()
        if not accounts:
            ttk.Label(frm,text="No hay cuentas en esta base/scope.\nCambiá a 'General' o creá cuentas en la base general.", foreground="#ff8080").grid(row=0,column=0,columnspan=2,sticky="w")
            ttk.Button(frm,text="Cerrar",command=win.destroy).grid(row=1,column=1,sticky="e",padx=6,pady=8); return
        acc_labels=[f\"{a['name']} ({a['currency']})\" for a in accounts]; acc_var=tk.StringVar(value=acc_labels[0])
        date_var=tk.StringVar(value=date.today().isoformat()); desc_var=tk.StringVar(value=""); monto_var=tk.StringVar(value=""); tipo_var=tk.IntVar(value=1)
        ttk.Label(frm,text="Cuenta").grid(row=0,column=0,sticky="w")
        ttk.Combobox(frm,values=acc_labels,state="readonly",width=40,textvariable=acc_var).grid(row=0,column=1,sticky="ew",padx=6,pady=4)
        ttk.Label(frm,text="Fecha (YYYY-MM-DD)").grid(row=1,column=0,sticky="w"); ttk.Entry(frm,width=16,textvariable=date_var).grid(row=1,column=1,sticky="w",padx=6,pady=4)
        ttk.Label(frm,text="Descripción").grid(row=2,column=0,sticky="w"); ttk.Entry(frm,width=42,textvariable=desc_var).grid(row=2,column=1,sticky="ew",padx=6,pady=4)
        ttk.Label(frm,text="Tipo").grid(row=3,column=0,sticky="w"); box=ttk.Frame(frm); box.grid(row=3,column=1,sticky="w",padx=6,pady=4)
        ttk.Radiobutton(box,text="Ingreso (+)",variable=tipo_var,value=1).pack(side=tk.LEFT,padx=(0,10))
        ttk.Radiobutton(box,text="Egreso (–)",variable=tipo_var,value=-1).pack(side=tk.LEFT)
        ttk.Label(frm,text="Monto (solo número)").grid(row=4,column=0,sticky="w"); ent_monto=ttk.Entry(frm,width=20,textvariable=monto_var); ent_monto.grid(row=4,column=1,sticky="w",padx=6,pady=4)
        bar=ttk.Frame(frm); bar.grid(row=5,column=0,columnspan=2,sticky="e",pady=(10,0))
        ttk.Button(bar,text="Cancelar",bootstyle=SECONDARY,command=win.destroy).pack(side=tk.RIGHT,padx=6)
        def _validar_fecha(s:str)->str:
            s=(s or "").strip()
            try: return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
            except Exception: raise ValueError("La fecha debe ser YYYY-MM-DD (ej: 2025-10-12).")
        def guardar():
            try:
                idx = acc_labels.index(acc_var.get()) if acc_var.get() in acc_labels else 0
                acc_id = accounts[idx]["id"]; posted=_validar_fecha(date_var.get())
                desc=(desc_var.get() or "").strip(); amt_raw=parse_amount(monto_var.get()); amt = abs(amt_raw) * (1 if tipo_var.get() >= 0 else -1)
                with connect(self.db_path) as con:
                    row=con.execute("SELECT currency FROM account WHERE id=?", (acc_id,)).fetchone()
                    if not row: raise RuntimeError("Cuenta no encontrada.")
                    con.execute("INSERT INTO transactions(account_id, posted_at, description, amount, currency) VALUES (?,?,?,?,?)",
                                (acc_id, posted, desc, amt, row[0]))
                win.destroy(); self.refresh_all()
            except ValueError as e:
                messagebox.showerror("Datos inválidos", f"{e}\n\nEjemplos válidos: 5000 | 5.000,00 | -1.200,50 | $ 1.234,56", parent=self)
            except Exception as e:
                messagebox.showerror("Error al guardar", str(e), parent=self)
        ttk.Button(bar,text="Guardar",bootstyle=SUCCESS,command=guardar).pack(side=tk.RIGHT)
        frm.columnconfigure(1,weight=1); win.bind("<Escape>", lambda e: win.destroy()); ent_monto.bind("<Return>", lambda e: guardar())
    def delete_selected_tx(self):
        sel=self.tv.selection(); if not sel: return
        tx_id=int(sel[0])
        if not messagebox.askyesno("Confirmar","¿Eliminar el movimiento seleccionado?"): return
        with connect(self.db_path) as con: con.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        self.refresh_all()
    def do_import(self):
        messagebox.showinfo("Importar (legacy)","Usá el botón Importar (Wizard) del header.")
    def export_to_excel(self):
        try:
            import pandas as pd
        except Exception:
            messagebox.showerror("Exportar","Necesitás instalar pandas y openpyxl para exportar a Excel."); return
        save_path=filedialog.asksaveasfilename(title="Guardar como", defaultextension=".xlsx",
                                               filetypes=[("Excel","*.xlsx"),("Todos","*.*")])
        if not save_path: return
        try:
            with connect(self.db_path) as con:
                acc=con.execute("SELECT id, name, currency FROM account ORDER BY name").fetchall()
                tx =con.execute("""SELECT t.id, COALESCE(t.posted_at, t.date) AS posted_at, t.description, t.amount, t.currency, a.name AS account_name
                                   FROM transactions t JOIN account a ON a.id=t.account_id ORDER BY posted_at, t.id""").fetchall()
            import pandas as pd
            df_acc = (pd.DataFrame(acc, columns=["id","name","currency"]) if acc else pd.DataFrame(columns=["id","name","currency"]))
            df_tx  = (pd.DataFrame(tx,  columns=["id","posted_at","description","amount","currency","account_name"]) if tx else
                      pd.DataFrame(columns=["id","posted_at","description","amount","currency","account_name"]))
            with pd.ExcelWriter(save_path, engine="openpyxl") as xw:
                df_acc.to_excel(xw, index=False, sheet_name="accounts")
                df_tx.to_excel(xw,  index=False, sheet_name="transactions")
            messagebox.showinfo("Exportar", f"Archivo guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Exportar", f"Error exportando: {e}")
if __name__ == "__main__":
    # Primer arranque: asegurar esquema general y un seed básico si está vacío
    from finanzasportable.services.db import ensure_schema, db_path_general, db_empty_of_core_tables
    p = db_path_general(); ensure_schema(p)
    if db_empty_of_core_tables(p):
        from pathlib import Path
        from finanzasportable.services.db import connect
        with connect(p) as con:
            con.execute("INSERT INTO institution(name,alias) VALUES (?,?)", ("Genérica","GEN"))
            inst_id = con.execute("SELECT id FROM institution WHERE name=?", ("Genérica",)).fetchone()[0]
            con.execute("INSERT INTO account(institution_id,name,type,currency,metadata) VALUES (?,?,?,?,?)",
                        (inst_id, "General", "wallet", "ARS", '{"position": 1}'))
            con.execute("INSERT OR IGNORE INTO category(name,type) VALUES ('Sueldo','IN'), ('Comida','OUT')")
    app = MPApp(); app.mainloop()
PY

# === 6) Script de seed opcional para año/mes ===
cat > scripts/seed_scope.py <<'PY'
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
PY

# === 7) README mínimo ===
cat > README.md <<'MD'
# Finanzas Portable (reconstruido)
- `python -m app.gui_mp` para lanzar la GUI.
- Bases: `data/general.db` (core), opcional `data/YYYY.db` y `data/YYYY-MM.db`.
- Importa CSV/Excel desde **Importar (Wizard)**.
MD

echo "▶ Proyecto listo."
echo "Siguiente paso:"
echo "1) source .venv/bin/activate"
echo "2) python -m app.gui_mp"

