#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

if [ ! -x .venv/bin/python ]; then
  echo "먼저 ./setup.sh를 실행해 주세요."
  exit 1
fi

.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --icon "assets/TistoryUploader.icns" \
  --collect-submodules selenium \
  --hidden-import selenium.webdriver.chrome \
  --hidden-import selenium.webdriver.chrome.options \
  --hidden-import selenium.webdriver.chrome.service \
  --name "티스토리 업로더" \
  --osx-bundle-identifier "com.local.tistory-uploader" \
  mac_app.py

echo "생성 완료: $APP_DIR/dist/티스토리 업로더.app"
