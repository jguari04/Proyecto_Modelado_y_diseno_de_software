#!/usr/bin/env bash
set -e

# Ir a la raíz del proyecto (este script vive en scripts/)
cd "$(dirname "$0")/.." || exit 1

echo "== 1) Creando entorno virtual (.venv)…"
python3 -m venv .venv
source .venv/bin/activate

echo "== 2) Instalando dependencias…"
pip install --upgrade pip
pip install -r requirements.txt

echo "== 3) Preparando carpeta de datos…"
mkdir -p data

echo "== 4) Verificando esquema de la DB…"
python3 - <<'PY'
from pathlib import Path
from src.finanzasportable.services.db import ensure_schema, db_path_general
g = db_path_general()
ensure_schema(g)
print(f"Esquema OK en {g}")
PY

echo "== 5) Listo. Para ejecutar:"
echo "source .venv/bin/activate && python -m app.gui_mp"

