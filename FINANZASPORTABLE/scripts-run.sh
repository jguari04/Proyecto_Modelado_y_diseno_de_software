#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
python -m app.gui_mp

