#!/usr/bin/env bash
set -u

PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
PYTHON_BIN="/usr/bin/python3"
HERMES_BIN="/Users/canerunal/.hermes/bin/hermes"
TELEGRAM_TO="telegram:6180022743"
cd "$PROJECT_DIR"

run_date=$(TZ=Europe/Istanbul date +%F)
echo "TAXONOMY_FINALIZE_START date=$run_date"

# Build before the data commit so the snapshot and its status travel together.
"$NODE_BIN" scripts/build_dashboard_status.cjs || echo "DASHBOARD_BUILD_WARN"

git add -f taxonomy dashboard scripts hermes README.md package.json .gitignore 2>/dev/null || true
first_commit=""
if ! git diff --cached --quiet; then
  if git commit -m "data: Hepsiburada taxonomy products ${run_date}"; then
    first_commit=$(git rev-parse --short HEAD)
  else
    echo "TAXONOMY_COMMIT_WARN"
  fi
fi

# Record the new source commit in the dashboard and commit that small update.
"$NODE_BIN" scripts/build_dashboard_status.cjs || echo "DASHBOARD_BUILD_WARN"
git add dashboard/status.json 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "ops: refresh Hepsiburada dashboard ${run_date}" 2>/dev/null || echo "DASHBOARD_COMMIT_WARN"
fi

push_status="SKIPPED"
if git push origin main 2>/dev/null; then
  push_status="PUSHED"
else
  push_status="PUSH_FAILED"
fi

message=$("$PYTHON_BIN" - <<'PY'
import datetime
import json
from pathlib import Path

root = Path("/Users/canerunal/Documents/Hepsiburada")
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
date = now.strftime("%Y-%m-%d")
summary = root / "taxonomy" / "snapshots" / date / "summary.json"
status = root / "taxonomy" / "status.json"
dashboard = root / "dashboard" / "status.json"
lines = [f"Hepsiburada taxonomy tamamlandi: {date}"]
if summary.exists():
    data = json.loads(summary.read_text())
    lines.append(f"Durum: {data.get('status')} | Urun: {data.get('productCount', 0)} | Uyelik: {data.get('rankingCount', 0)} | Kok: {data.get('rootCount', 0)}/{data.get('expectedRootCount', 9)}")
    for shard in data.get("shards", []):
        for root_row in shard.get("roots", []):
            lines.append(f"{root_row.get('root_name')}: {root_row.get('unique_product_count', 0)}/{root_row.get('target', 0)}")
elif status.exists():
    data = json.loads(status.read_text())
    lines.append(f"Taxonomy status: {data.get('status')} ({data.get('reason', '')})")
else:
    lines.append("Taxonomy ozeti bulunamadi; uretilen dosyalar yine GitHub'a yedeklendi.")
if dashboard.exists():
    data = json.loads(dashboard.read_text())
    lines.append(f"Dashboard: {data.get('generatedAt')}")
print("\n".join(lines))
PY
)
message="${message}"$'\nGitHub: '"${push_status}"
echo "$message"
echo "$message" | "$HERMES_BIN" send --to "$TELEGRAM_TO" 2>&1 || echo "TELEGRAM_ATLANDI"
echo "TAXONOMY_FINALIZE_OK first_commit=${first_commit:-none} push=$push_status"
