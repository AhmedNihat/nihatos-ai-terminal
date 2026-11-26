#!/usr/bin/env bash
set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$HOME"
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/gui.py" "$@"
