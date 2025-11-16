#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
pyinstaller --noconfirm --clean \
  --name "Finanzas Portable" \
  --add-data "src:src" --add-data "app:app" \
  -p "src" -p "app" \
  -w app/gui_mp.py
echo "Build listo en dist/Finanzas Portable/"

