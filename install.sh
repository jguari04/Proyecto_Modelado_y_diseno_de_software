#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$PWD/src:$PYTHONPATH"
python3 -m app.gui_mp
