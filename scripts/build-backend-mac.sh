#!/usr/bin/env bash
# 在 macOS 上打包 Python 后端为 PyInstaller onefile，并复制为 Tauri sidecar。
# 用法：bash scripts/build-backend-mac.sh [aarch64-apple-darwin|x86_64-apple-darwin]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/apps/backend"
TRIPLE="${1:-aarch64-apple-darwin}"

cd "$BACKEND"
python3 -m PyInstaller \
  --noconfirm --clean \
  --onefile \
  --name ai-drama-backend \
  --collect-data docx \
  --add-data "$BACKEND/app/db/schema.sql:app/db" \
  --add-data "$BACKEND/app/services/vendor_models.json:app/services" \
  --hidden-import keyring.backends.macOS \
  --distpath dist-bundle-mac \
  --workpath build/pyinstaller-mac \
  --specpath build \
  server_entry.py

SIDECAR_DIR="$ROOT/apps/desktop/src-tauri/binaries"
SIDECAR="$SIDECAR_DIR/ai-drama-backend-$TRIPLE"
mkdir -p "$SIDECAR_DIR"
cp dist-bundle-mac/ai-drama-backend "$SIDECAR"
chmod +x "$SIDECAR"
echo "Backend bundled: $SIDECAR"
