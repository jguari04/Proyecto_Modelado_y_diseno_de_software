# check_project.py
# Auditoría simple para "Finanzas Portable"
from __future__ import annotations
import sys, os, re, json, argparse
from pathlib import Path
from importlib import import_module

OK   = "✅"
WARN = "⚠️"
BAD  = "❌"

def add_src_to_syspath(root: Path):
    src = root / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def check_structure(root: Path):
    items = {
        "app_gui": (root/"app"/"gui_mp.py").is_file(),
        "src_pkg": (root/"src"/"finanzasportable").is_dir(),
        "services_db": (root/"src"/"finanzasportable"/"services"/"db.py").is_file(),
    }
    score = all(items.values())
    details = []
    details.append(f"{OK if items['app_gui'] else BAD} app/gui_mp.py")
    details.append(f"{OK if items['src_pkg'] else BAD} src/finanzasportable/")
    details.append(f"{OK if items['services_db'] else BAD} src/finanzasportable/services/db.py")
    return score, details

def check_classes_and_design(root: Path):
    add_src_to_syspath(root)
    ok = True
    details = []
    # GUI classes
    try:
        gui = import_module("app.gui_mp".replace("/", "."))
        has_app = hasattr(gui, "MPApp")
        has_wiz = hasattr(gui, "ImportWizard")
        ok = ok and has_app and has_wiz
        details.append(f"{OK if has_app else BAD} clase MPApp en app/gui_mp.py")
        details.append(f"{OK if has_wiz else BAD} clase ImportWizard en app/gui_mp.py")
    except Exception as e:
        ok = False
        details.append(f"{BAD} No se pudo importar app/gui_mp.py ({e.__class__.__name__})")
    # DB helpers
    try:
        db = import_module("finanzasportable.services.db")
        has_connect = hasattr(db, "connect")
        has_ensure  = hasattr(db, "ensure_schema")
        ok = ok and has_connect and has_ensure
        details.append(f"{OK if has_connect else BAD} función connect()")
        details.append(f"{OK if has_ensure else BAD} función ensure_schema()")
    except Exception as e:
        ok = False
        details.append(f"{BAD} No se pudo importar services/db.py ({e.__class__.__name__})")
    return ok, details

def check_hardcode(root: Path):
    # buscá SQL o datos “quemados” peligrosos en GUI (muy básico)
    gui = (root/"app"/"gui_mp.py")
    txt = read_text_safe(gui)
    # considerar “SELECT … INSERT … UPDATE … DELETE” en GUI como potencialmente no-capa
    sql_in_gui = bool(re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", txt, re.I))
    # considerar hardcode típico: montos fijos en GUI (no en comentarios)
    money_literals = re.findall(r"(?<!#).*?\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\b", txt)
    # No vamos a fallar por números sueltos (pueden ser UI), solo advertir si hay muchos
    too_many_numbers = len(money_literals) >= 5
    ok = not sql_in_gui
    details = []
    details.append(f"{OK if not sql_in_gui else WARN} SQL en GUI (mejor mover a services/): {'sí' if sql_in_gui else 'no'}")
    if too_many_numbers:
        details.append(f"{WARN} Hay varios números literales en GUI (ver si son textos de UI o montos hardcodeados).")
    return ok, details

def check_persistence_and_schema(root: Path):
    add_src_to_syspath(root)
    details = []
    ok = True
    try:
        db = import_module("finanzasportable.services.db")
        general = db.db_path_general()
        # asegurar carpeta y esquema
        db.ensure_schema(general)
        # abrir y chequear tablas mínimas
        with db.connect(general) as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed = {"institution", "account", "category", "transactions"}
        missing = needed - tables
        ok = ok and not missing
        details.append(f"{OK if not missing else BAD} Tablas base: {', '.join(sorted(needed))}" + ("" if not missing else f" (faltan: {', '.join(sorted(missing))})"))
        details.append(f"{OK} archivo BD: {general}")
    except Exception as e:
        ok = False
        details.append(f"{BAD} Error de persistencia/esquema: {e}")
    return ok, details

def check_layers(root: Path):
    # capa: verificar que GUI no haga import directo de sqlite3
    gui = (root/"app"/"gui_mp.py")
    txt = read_text_safe(gui)
    imports_sqlite_in_gui = "import sqlite3" in txt or "from sqlite3" in txt
    ok = not imports_sqlite_in_gui
    details = [f"{OK if not imports_sqlite_in_gui else WARN} GUI sin importar sqlite3 directamente"]
    return ok, details

def check_installer_and_reqs(root: Path, fix: bool):
    reqs = root/"requirements.txt"
    sh   = root/"install.sh"
    ok = reqs.is_file() and sh.is_file()
    details = []
    if reqs.is_file():
        details.append(f"{OK} requirements.txt")
    else:
        details.append(f"{WARN} Falta requirements.txt")
    if sh.is_file():
        details.append(f"{OK} install.sh")
    else:
        details.append(f"{WARN} Falta install.sh")

    if fix:
        if not reqs.is_file():
            reqs.write_text("ttkbootstrap\npandas\nopenpyxl\n", encoding="utf-8")
            details.append(f"{OK} Creado requirements.txt")
        if not sh.is_file():
            sh.write_text(
                "#!/usr/bin/env bash\n"
                "set -e\n"
                "python3 -m venv .venv\n"
                "source .venv/bin/activate\n"
                "pip install -r requirements.txt\n"
                "export PYTHONPATH=\"$PWD/src:$PYTHONPATH\"\n"
                "python3 -m app.gui_mp\n",
                encoding="utf-8"
            )
            os.chmod(sh, 0o755)
            details.append(f"{OK} Creado install.sh (ejecutar: ./install.sh)")
        ok = True
    return ok, details

def print_section(title: str, details: list[str], ok: bool):
    bar = "="*70
    print(f"\n{bar}\n{title} — {'OK' if ok else 'REVISAR'}\n{bar}")
    for d in details:
        print(" -", d)

def main():
    parser = argparse.ArgumentParser(description="Auditoría de proyecto (POO) — Finanzas Portable")
    parser.add_argument("--fix", action="store_true", help="crear requirements.txt e install.sh si faltan")
    args = parser.parse_args()

    root = Path.cwd()
    print(f"📁 Proyecto: {root}")

    results = []

    ok, det = check_structure(root)
    print_section("1) ESTRUCTURA BÁSICA", det, ok); results.append(ok)

    ok, det = check_classes_and_design(root)
    print_section("2) DISEÑO DE CLASES", det, ok); results.append(ok)

    ok, det = check_hardcode(root)
    print_section("3) CÓDIGO HARDCODEADO", det, ok); results.append(ok)

    ok, det = check_persistence_and_schema(root)
    print_section("4) PERSISTENCIA / ESQUEMA", det, ok); results.append(ok)

    ok, det = check_layers(root)
    print_section("5) CAPAS", det, ok); results.append(ok)

    ok, det = check_installer_and_reqs(root, fix=args.fix)
    print_section("6) INSTALADOR / DEPENDENCIAS", det, ok); results.append(ok)

    passed = all(results)
    print("\nResumen:", OK if passed else WARN, "—",
          "Todo en orden" if passed else "Hay puntos para ajustar (ver secciones arriba)")
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()

