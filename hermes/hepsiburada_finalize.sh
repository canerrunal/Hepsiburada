#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
PYTHON_BIN="/usr/bin/python3"
HERMES_BIN="/Users/canerunal/.hermes/bin/hermes"
TELEGRAM_TO="telegram:6180022743"
cd "$PROJECT_DIR"
/usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock "$NODE_BIN" scripts/publish_website.cjs

digest="$("$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
root = Path("/Users/canerunal/Documents/Hepsiburada")
lines = ["Hepsiburada gunluk ozet"]
files = [root / "reports" / "telegram-latest.txt"] + sorted((root / "categories").glob("*/reports/telegram-latest.txt"))
for f in files:
    if f.exists():
        lines.append(f.read_text().strip())
quals = []
q = root / "quality" / "latest.json"
if q.exists():
    j = json.loads(q.read_text())
    quals.append(f"elektronik:{j.get('status')}/{j.get('productCount')}")
for qf in sorted((root / "categories").glob("*/quality/latest.json")):
    j = json.loads(qf.read_text())
    quals.append(f"{qf.parent.parent.name}:{j.get('status')}/{j.get('productCount')}")
lines.append("Kalite: " + ", ".join(quals))
print("\n".join(lines))
PY
)"
echo "$digest"
echo "$digest" | "$HERMES_BIN" send --to "$TELEGRAM_TO" 2>&1 || echo "TELEGRAM_ATLANDI"
echo "FINALIZE_JOB_OK time=$(TZ=Europe/Istanbul date +%FT%T%z)"
