# scripts/add_managers.py
from pathlib import Path
import re
from datetime import datetime

GUI = Path("app/gui_mp.py")
assert GUI.exists(), "No se encontró app/gui_mp.py (parate en la carpeta del proyecto)."

src = GUI.read_text(encoding="utf-8")
backup = Path(f"app/gui_mp.py.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
backup.write_text(src, encoding="utf-8")

changed = False

# Insertar botones de Cuentas y Categorías debajo del botón Exportar
pat = re.compile(r'^(?P<indent>\s*)ttk\.Button\([^\\n]*command=self\.export_to_excel\)\.pack[^\n]*$', re.M)
m = pat.search(src)
if m and "open_accounts_manager" not in src:
    indent = m.group("indent")
    insert = (
        f'\n{indent}ttk.Button(btns, text="Cuentas", bootstyle=SECONDARY, '
        f'command=self.open_accounts_manager).pack(side=tk.LEFT, padx=6)'
        f'\n{indent}ttk.Button(btns, text="Categorías", bootstyle=SECONDARY, '
        f'command=self.open_categories_manager).pack(side=tk.LEFT, padx=6)\n'
    )
    src = src[:m.end()] + insert + src[m.end():]
    changed = True

# Insertar los dos métodos nuevos al final de la clase MPApp
if "def open_accounts_manager(self):" not in src:
    add_code = """

    def open_accounts_manager(self):
        import tkinter as tk
        from tkinter import simpledialog, messagebox
        from finanzasportable.services.db import connect, db_path_general

        db = db_path_general()
        win = tk.Toplevel(self)
        win.title("Gestor de cuentas")
        win.geometry("520x420")

        listbox = tk.Listbox(win)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load_accounts():
            listbox.delete(0, tk.END)
            with connect(db) as con:
                for r in con.execute("SELECT name, currency, type FROM account ORDER BY name"):
                    listbox.insert(tk.END, f"{r['name']} ({r['currency']}) [{r['type']}]")

        def add_account():
            name = simpledialog.askstring("Nueva cuenta", "Nombre de la cuenta:", parent=win)
            if not name:
                return
            currency = simpledialog.askstring("Moneda", "Ej: ARS, USD:", parent=win) or "ARS"
            acc_type = simpledialog.askstring("Tipo", "Ej: Caja, Banco, MP, etc:", parent=win) or ""
            with connect(db) as con:
                con.execute(
                    "INSERT OR IGNORE INTO account(name, currency, type) VALUES (?, ?, ?)",
                    (name, currency, acc_type)
                )
            load_accounts()
            messagebox.showinfo("OK", "Cuenta creada correctamente.\\nSe replicará en todos los meses.", parent=win)
            self.refresh_all()

        def edit_account():
            sel = listbox.curselection()
            if not sel:
                return
            old_name = listbox.get(sel[0]).split(" (")[0]
            new_name = simpledialog.askstring("Editar cuenta", "Nuevo nombre:", initialvalue=old_name, parent=win)
            if not new_name:
                return
            with connect(db) as con:
                con.execute("UPDATE account SET name=? WHERE name=?", (new_name, old_name))
            load_accounts()
            messagebox.showinfo("OK", "Nombre actualizado.", parent=win)
            self.refresh_all()

        def delete_account():
            sel = listbox.curselection()
            if not sel:
                return
            name = listbox.get(sel[0]).split(" (")[0]
            if not messagebox.askyesno("Confirmar", f"¿Eliminar cuenta '{name}'?", parent=win):
                return
            with connect(db) as con:
                con.execute("DELETE FROM account WHERE name=?", (name,))
            load_accounts()
            messagebox.showinfo("OK", "Cuenta eliminada.", parent=win)
            self.refresh_all()

        tk.Button(win, text="➕ Añadir", command=add_account).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="✏️ Editar", command=edit_account).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="🗑️ Eliminar", command=delete_account).pack(side=tk.LEFT, padx=10, pady=5)

        load_accounts()


    def open_categories_manager(self):
        import tkinter as tk
        from tkinter import simpledialog, messagebox
        from finanzasportable.services.db import connect, db_path_general

        db = db_path_general()
        win = tk.Toplevel(self)
        win.title("Gestor de categorías")
        win.geometry("420x360")

        listbox = tk.Listbox(win)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load_cats():
            listbox.delete(0, tk.END)
            with connect(db) as con:
                for r in con.execute("SELECT name FROM category ORDER BY name"):
                    listbox.insert(tk.END, r["name"])

        def add_cat():
            name = simpledialog.askstring("Nueva categoría", "Nombre de la categoría:", parent=win)
            if not name:
                return
            with connect(db) as con:
                con.execute("INSERT OR IGNORE INTO category(name) VALUES (?)", (name,))
            load_cats()
            messagebox.showinfo("OK", "Categoría creada correctamente.", parent=win)
            self.refresh_all()

        def edit_cat():
            sel = listbox.curselection()
            if not sel:
                return
            old_name = listbox.get(sel[0])
            new_name = simpledialog.askstring("Editar categoría", "Nuevo nombre:", initialvalue=old_name, parent=win)
            if not new_name:
                return
            with connect(db) as con:
                con.execute("UPDATE category SET name=? WHERE name=?", (new_name, old_name))
            load_cats()
            messagebox.showinfo("OK", "Nombre actualizado.", parent=win)
            self.refresh_all()

        def delete_cat():
            sel = listbox.curselection()
            if not sel:
                return
            name = listbox.get(sel[0])
            if not messagebox.askyesno("Confirmar", f"¿Eliminar categoría '{name}'?", parent=win):
                return
            with connect(db) as con:
                con.execute("DELETE FROM category WHERE name=?", (name,))
            load_cats()
            messagebox.showinfo("OK", "Categoría eliminada.", parent=win)
            self.refresh_all()

        tk.Button(win, text="➕ Añadir", command=add_cat).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="✏️ Editar", command=edit_cat).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="🗑️ Eliminar", command=delete_cat).pack(side=tk.LEFT, padx=10, pady=5)

        load_cats()
    """
    src = src.rstrip() + "\n" + add_code
    changed = True

if changed:
    GUI.write_text(src, encoding="utf-8")
    print("✅ Parche aplicado correctamente. Se agregaron botones y gestores.")
    print(f"   Backup guardado en: {backup}")
else:
    print("ℹ️ Todo ya estaba aplicado. No se hicieron cambios.")

