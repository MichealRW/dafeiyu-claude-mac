#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This app bundle must be built on macOS."
  exit 1
fi
python -m PyInstaller --noconfirm app.spec
codesign --verify --deep --strict "dist/大肥鱼桌宠.app"
echo "Built: dist/大肥鱼桌宠.app"
