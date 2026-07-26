#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

if [ -d "dist/티스토리 업로더.app" ]; then
  open "dist/티스토리 업로더.app"
  exit 0
fi

if [ ! -x .venv/bin/python ]; then
  osascript -e 'display alert "티스토리 업로더" message "먼저 setup.sh를 한 번 실행해 주세요."' 2>/dev/null || true
  exit 1
fi

exec .venv/bin/python mac_app.py
