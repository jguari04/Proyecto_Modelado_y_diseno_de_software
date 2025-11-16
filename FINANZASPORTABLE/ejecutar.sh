#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
python3 -m app.gui_mp
