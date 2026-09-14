#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
cd "$PROJECT_DIR"
export HB_HEADLESS="${HB_HEADLESS:-1}"

/usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock bash -c '
  set -euo pipefail
  cd "/Users/canerunal/Documents/Hepsiburada"
  pids=()
  run_shard() {
    local tag="$1" seeds="$2"
    /usr/bin/python3 scripts/run_with_timeout.py --timeout 14400 --heartbeat 60 -- \
      /usr/bin/python3 scripts/hb_taxonomy_crawl.py --seeds "$seeds" --tag "$tag" &
    pids+=("$!")
  }
  run_shard shard-0 "0,1,2"
  run_shard shard-1 "3,4"
  run_shard shard-2 "5,6"
  run_shard shard-3 "7,8"
  failed=0
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  if [[ "$failed" -ne 0 ]]; then
    echo "TAXONOMY_SHARDS_FAIL" >&2
    exit 2
  fi
  /usr/bin/python3 scripts/hb_taxonomy_merge.py --tags shard-0,shard-1,shard-2,shard-3

  product_pids=()
  for shard in 0 1 2 3; do
    /usr/bin/python3 scripts/run_with_timeout.py --timeout 21600 --heartbeat 60 -- \
      /usr/bin/python3 scripts/hb_taxonomy_collect.py --shard "$shard" --of 4 &
    product_pids+=("$!")
  done
  product_failed=0
  for pid in "${product_pids[@]}"; do wait "$pid" || product_failed=1; done
  if [[ "$product_failed" -eq 0 ]]; then
    /usr/bin/python3 scripts/hb_taxonomy_collect_merge.py --date "$(TZ=Europe/Istanbul date +%F)" --of 4 || product_failed=1
  fi
  if [[ "$product_failed" -ne 0 ]]; then
    echo "TAXONOMY_PRODUCT_COLLECTION_INSUFFICIENT_OR_FAILED" >&2
  fi
  /Users/canerunal/.local/bin/node scripts/build_dashboard_status.cjs
'

run_date=$(TZ=Europe/Istanbul date +%F)
git add taxonomy 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "data: Hepsiburada taxonomy ${run_date}" 2>/dev/null || true
  git push origin main 2>/dev/null || echo "PUSH_ATLANDI"
fi
echo "DISCOVERY_JOB_OK ${run_date}"
