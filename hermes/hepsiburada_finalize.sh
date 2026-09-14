#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
cd "$PROJECT_DIR"
/usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock "$NODE_BIN" scripts/publish_website.cjs
echo "FINALIZE_JOB_OK time=$(TZ=Europe/Istanbul date +%FT%T%z)"
echo "Telegram özetleri: categories/*/reports/telegram-latest.txt (bot hazır olunca gönderilir)"
