#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "[NihatOS Terminal] Checking system Python..."
python3 --version

if [ ! -d ".venv" ]; then
    echo "[NihatOS Terminal] Creating project-local virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "[NihatOS Terminal] Installing dependencies into .venv (no global changes, no sudo)..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

chmod 444 app/shell/nihatos_bashrc

echo "[NihatOS Terminal] Setup complete."