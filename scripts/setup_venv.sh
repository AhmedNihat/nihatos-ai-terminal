#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "[N1BroX Terminal] Checking system Python..."
python3 --version

if [ ! -d ".venv" ]; then
    echo "[N1BroX Terminal] Creating project-local virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "[N1BroX Terminal] Installing dependencies into .venv (no global changes, no sudo)..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

chmod 444 app/shell/n1brox_bashrc

echo "[N1BroX Terminal] Setup complete."