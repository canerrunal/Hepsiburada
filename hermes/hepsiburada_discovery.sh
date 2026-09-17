#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/canerunal/Documents/Hepsiburada"
cd "$PROJECT_DIR"
export HB_HEADLESS="${HB_HEADLESS:-1}"
export HB_TAXONOMY_HEADLESS="${HB_TAXONOMY_HEADLESS:-0}"
export HB_TAXONOMY_REQUEST_DELAY_MS="${HB_TAXONOMY_REQUEST_DELAY_MS:-5000}"

/usr/bin/lockf -t 900 /tmp/hepsiburada-daily-global.lock bash -c '
  set -euo pipefail
  cd "/Users/canerunal/Documents/Hepsiburada"
  taxonomy_browser_mode=(--headed)
  if [[ "${HB_TAXONOMY_HEADLESS:-0}" == "1" ]]; then
    taxonomy_browser_mode=(--headless)
  fi
  taxonomy_request_delay="${HB_TAXONOMY_REQUEST_DELAY_MS:-5000}"
  pids=()
  run_shard() {
    local tag="$1" seeds="$2"
    /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/run_with_timeout.py --timeout 14400 --heartbeat 60 -- \
      /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/hb_taxonomy_crawl.py --seeds "$seeds" --tag "$tag" "${taxonomy_browser_mode[@]}" &
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
  /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/hb_taxonomy_merge.py --tags shard-0,shard-1,shard-2,shard-3

  product_pids=()
  for shard in 0 1 2 3; do
      /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/run_with_timeout.py --timeout 21600 --heartbeat 60 -- \
      /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/hb_taxonomy_collect.py --shard "$shard" --of 4 --category-scope root "${taxonomy_browser_mode[@]}" --request-delay-ms "$taxonomy_request_delay" &
    product_pids+=("$!")
  done
  product_failed=0
  for pid in "${product_pids[@]}"; do wait "$pid" || product_failed=1; done
  if [[ "$product_failed" -eq 0 ]]; then
    /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3 scripts/hb_taxonomy_collect_merge.py --date "$(TZ=Europe/Istanbul date +%F)" --of 4 || product_failed=1
  fi
  if [[ "$product_failed" -ne 0 ]]; then
    echo "TAXONOMY_PRODUCT_COLLECTION_INSUFFICIENT_OR_FAILED" >&2
  fi
  bash scripts/finalize_taxonomy_collection.sh
'

run_date=$(TZ=Europe/Istanbul date +%F)
git add taxonomy 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "data: Hepsiburada taxonomy ${run_date}" 2>/dev/null || true
  git push origin main 2>/dev/null || echo "PUSH_ATLANDI"
fi
echo "DISCOVERY_JOB_OK ${run_date}"
