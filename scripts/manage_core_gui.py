import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path
from finanzasportable.services.db import connect, db_path_general
from finanzasportable.services.core_sync import ensure_core_cloned

DBDIR = (Path(__file__).resolve().parents[1] / "data")

class CoreManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Cuentas y Categorías (GENERAL)")
        self.geometry("600x420")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Cuentas ---
        frm_acc = ttk.Frame(nb); nb.add(frm_acc, text="Cuentas")
        self.lst_acc = tk.Listbox(frm_acc)
        self.lst_acc.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        acc_btns = ttk.Frame(frm_acc); acc_btns.pack(side="right", fill="y", padx=5)
        ttk.Button(acc_btns, text="+ Añadir", command=self.add_account).pack(fill="x", pady=3)
        ttk.Button(acc_btns, text="✎ Editar", command=self.edit_account).pack(fill="x", pady=3)
        ttk.Button(acc_btns, text="🗑 Eliminar", command=self.del_account).pack(fill="x", pady=3)

        # --- Categorías ---
        frm_cat = ttk.Frame(nb); nb.add(frm_cat, text="Categorías")
        self.lst_cat = tk.Listbox(frm_cat)
        self.lst_cat.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        cat_btns = ttk.Frame(frm_cat); cat_btns.pack(side="right", fill="y", padx=5)
        ttk.Button(cat_btns, text="+ Añadir", command=self.add_category).pack(fill="x", pady=3)
        ttk.Button(cat_btns, text="✎ Editar", command=self.edit_category).pack(fill="x", pady=3)
        ttk.Button(cat_btns, text="🗑 Eliminar", command=self.del_category).pack(fill="x", pady=3)

        # --- Sincronizar ---
        ttk.Button(self, text="🔄 Sincronizar a todos los meses", command=self.sync_all).pack(pady=6)

        self.refresh()

    def refresh(self):
        gdb = db_path_general()
        with connect(gdb) as con:
            accs = con.execute("SELECT name FROM account ORDER BY name").fetchall()
            cats = con.execute("SELECT name FROM category ORDER BY name").fetchall()
        self.lst_acc.delete(0, tk.END)
        for r in accs: self.lst_acc.insert(tk.END, r["name"])
        self.lst_cat.delete(0, tk.END)
        for r in cats: self.lst_cat.insert(tk.END, r["name"])

    # ---- cuentas
    def add_account(self):
        name = simpledialog.askstring("Nueva cuenta", "Nombre:", parent=self)
        if not name: return
        with connect(db_path_general()) as con:
            con.execute("INSERT OR IGNORE INTO account(name,currency,type) VALUES (?,?,?)",
                        (name, "ARS", "wallet"))
        self.refresh(); messagebox.showinfo("OK", f"Cuenta '{name}' creada.", parent=self)

    def edit_account(self):
        sel = self.lst_acc.curselection()
        if not sel: return
        old = self.lst_acc.get(sel)
        new = simpledialog.askstring("Editar cuenta", "Nuevo nombre:", initialvalue=old, parent=self)
        if not new: return
        with connect(db_path_general()) as con:
            con.execute("UPDATE account SET name=? WHERE name=?", (new, old))
        self.refresh(); messagebox.showinfo("OK", f"Renombrada: {old} → {new}", parent=self)

    def del_account(self):
        sel = self.lst_acc.curselection()
        if not sel: return
        name = self.lst_acc.get(sel)
        if not messagebox.askyesno("Eliminar", f"¿Eliminar '{name}'?", parent=self): return
        with connect(db_path_general()) as con:
            con.execute("DELETE FROM account WHERE name=?", (name,))
        self.refresh(); messagebox.showinfo("OK", f"Cuenta '{name}' eliminada.", parent=self)

    # ---- categorías
    def add_category(self):
        name = simpledialog.askstring("Nueva categoría", "Nombre:", parent=self)
        if not name: return
        with connect(db_path_general()) as con:
            con.execute("INSERT OR IGNORE INTO category(name) VALUES (?)", (name,))
        self.refresh(); messagebox.showinfo("OK", f"Categoría '{name}' creada.", parent=self)

    def edit_category(self):
        sel = self.lst_cat.curselection()
        if not sel: return
        old = self.lst_cat.get(sel)
        new = simpledialog.askstring("Editar categoría", "Nuevo nombre:", initialvalue=old, parent=self)
        if not new: return
        with connect(db_path_general()) as con:
            con.execute("UPDATE category SET name=? WHERE name=?", (new, old))
        self.refresh(); messagebox.showinfo("OK", f"Renombrada: {old} → {new}", parent=self)

    def del_category(self):
        sel = self.lst_cat.curselection()
        if not sel: return
        name = self.lst_cat.get(sel)
        if not messagebox.askyesno("Eliminar", f"¿Eliminar '{name}'?", parent=self): return
        with connect(db_path_general()) as con:
            con.execute("DELETE FROM category WHERE name=?", (name,))
        self.refresh(); messagebox.showinfo("OK", f"Categoría '{name}' eliminada.", parent=self)

    # ---- sincronizar core GENERAL → todos los .db
    def sync_all(self):
        count = 0
        for p in sorted(DBDIR.glob("*.db")):
            if p.name == "general.db":
                continue
            ensure_core_cloned(p)  # recibe Path
            count += 1
        messagebox.showinfo("Sincronizado", f"Core replicado a {count} bases (mes/año).", parent=self)
        self.refresh()

if __name__ == "__main__":
    CoreManager().mainloop()
