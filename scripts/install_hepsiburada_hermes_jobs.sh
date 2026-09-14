#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
HERMES_BIN="/Users/canerunal/.hermes/bin/hermes"
HERMES_SCRIPT_DIR="/Users/canerunal/.hermes/scripts"
JOBS_FILE="/Users/canerunal/.hermes/cron/jobs.json"

mkdir -p "$HERMES_SCRIPT_DIR"
for source in "$PROJECT_DIR"/hermes/hepsiburada_*.sh; do
  install -m 755 "$source" "$HERMES_SCRIPT_DIR/$(basename "$source")"
done

job_id_for_name() {
  /usr/bin/python3 - "$JOBS_FILE" "$1" <<'PY'
import json, pathlib, sys
file, name = pathlib.Path(sys.argv[1]), sys.argv[2]
if file.exists():
    for job in json.loads(file.read_text()).get('jobs', []):
        if job.get('name') == name:
            print(job.get('id', ''))
            break
PY
}

upsert_job() {
  local name="$1" schedule="$2" script="$3" deliver="$4"
  local job_id
  job_id="$(job_id_for_name "$name")"
  if [[ -n "$job_id" ]]; then
    "$HERMES_BIN" cron edit "$job_id" --schedule "$schedule" --name "$name" --deliver "$deliver" --script "$script" --no-agent --workdir "$PROJECT_DIR"
  else
    "$HERMES_BIN" cron create "$schedule" --name "$name" --deliver "$deliver" --script "$script" --no-agent --workdir "$PROJECT_DIR"
  fi
}

upsert_job "hepsiburada-discovery" "0 15 * * *" "hepsiburada_discovery.sh" "local"
upsert_job "hepsiburada-elektronik" "30 22 * * *" "hepsiburada_elektronik.sh" "local"
upsert_job "hepsiburada-moda" "0 23 * * *" "hepsiburada_moda.sh" "local"
upsert_job "hepsiburada-supermarket" "30 23 * * *" "hepsiburada_supermarket.sh" "local"
upsert_job "hepsiburada-kozmetik" "0 0 * * *" "hepsiburada_kozmetik.sh" "local"
upsert_job "hepsiburada-anne-bebek" "30 0 * * *" "hepsiburada_anne_bebek.sh" "local"
upsert_job "hepsiburada-finalize" "30 4 * * *" "hepsiburada_finalize.sh" "local"

echo "HEPSIBURADA_HERMES_INSTALL_OK jobs=7"
