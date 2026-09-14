#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
cd "$PROJECT_DIR"
/usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock "$NODE_BIN" scripts/discover_hepsiburada_taxonomy.cjs
run_date=$(TZ=Europe/Istanbul date +%F)
git add taxonomy 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "data: Hepsiburada kategori keşfi ${run_date}" 2>/dev/null || true
  git push origin main 2>/dev/null || echo "PUSH_ATLANDI"
fi
echo "DISCOVERY_JOB_OK ${run_date}"
