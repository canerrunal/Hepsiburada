#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
PYTHON_BIN="/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3"
HERMES_BIN="/Users/canerunal/.hermes/bin/hermes"
TELEGRAM_TO="telegram:6180022743"
cd "$PROJECT_DIR"

quality_failed=0
for profile in elektronik moda supermarket kozmetik anne-bebek-oyuncak; do
  if ! "$NODE_BIN" scripts/quality_check.cjs --profile "$profile" --phase final; then
    quality_failed=1
  fi
done
"$NODE_BIN" scripts/build_dashboard_status.cjs

if [[ "$quality_failed" -eq 0 ]]; then
  /usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock "$NODE_BIN" scripts/publish_website.cjs
else
  echo "PUBLISH_SKIP quality gate başarısız; son geçerli snapshot korunuyor"
fi

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
