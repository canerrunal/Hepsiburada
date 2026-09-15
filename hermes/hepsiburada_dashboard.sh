#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
cd "$PROJECT_DIR"
/Users/canerunal/.local/bin/node scripts/build_dashboard_status.cjs
run_date=$(TZ=Europe/Istanbul date +%F)
git add dashboard/status.json 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "data: dashboard status ${run_date}" 2>/dev/null || true
  git push origin main 2>/dev/null || echo "PUSH_ATLANDI"
fi
