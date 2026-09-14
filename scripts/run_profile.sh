#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
NODE_BIN="/Users/canerunal/.local/bin/node"
PYTHON_BIN="/usr/bin/python3"
PROFILE="${1:-elektronik}"

if [[ ! "$PROFILE" =~ ^[a-z0-9-]+$ ]]; then
  echo "Geçersiz profil: $PROFILE" >&2
  exit 2
fi

if [[ "${HEPSIBURADA_GLOBAL_LOCK_HELD:-0}" != "1" ]]; then
  export HEPSIBURADA_GLOBAL_LOCK_HELD=1
  echo "GLOBAL_LOCK_WAIT profile=$PROFILE"
  exec /usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock "$0" "$PROFILE"
fi

cd "$PROJECT_DIR"

echo "DAILY_RUN_START profile=$PROFILE time=$(TZ=Europe/Istanbul date +%FT%T%z)"

run_collector() {
  "$PYTHON_BIN" scripts/run_with_timeout.py --timeout 1200 --heartbeat 30 -- \
    "$PYTHON_BIN" scripts/hb_collect_pw.py --profile "$PROFILE"
}

if ! run_collector; then
  echo "İlk toplama denemesi başarısız: $PROFILE. 120 saniye sonra bir kez daha denenecek." >&2
  sleep 120
  run_collector
fi
"$NODE_BIN" scripts/quality_check.cjs --profile "$PROFILE"

echo "DETAIL_RUN_START profile=$PROFILE"
if "$PYTHON_BIN" scripts/run_with_timeout.py --timeout 4200 --heartbeat 60 -- \
  "$PYTHON_BIN" scripts/hb_detail_pw.py --profile "$PROFILE"; then
  "$PYTHON_BIN" scripts/hb_detail_merge.py --profile "$PROFILE" --of 1
else
  echo "Detay turu zaman asimi/hatasi: kalanlar yarin tamamlanir (resume)." >&2
  "$PYTHON_BIN" scripts/hb_detail_merge.py --profile "$PROFILE" --of 1 || true
fi

run_date=$(TZ=Europe/Istanbul date +%F)
if [[ "$PROFILE" == "elektronik" ]]; then
  git add data snapshots lists reports quality taxonomy scripts 2>/dev/null || true
else
  git add "categories/$PROFILE" taxonomy 2>/dev/null || true
fi
if ! git diff --cached --quiet; then
  git commit -m "data: Hepsiburada ${PROFILE} günlük raporu ${run_date}" 2>/dev/null || true
  git push origin main 2>/dev/null || echo "PUSH_ATLANDI (uzak yazma yok)"
fi

echo "DAILY_RUN_OK ${PROFILE} ${run_date}"
