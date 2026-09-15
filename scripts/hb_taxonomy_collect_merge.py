#!/usr/bin/env python3
"""Merge taxonomy product shards into one date-stamped snapshot."""
import argparse
import gzip
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ROOT_COUNT = 9

try:
    from atomic_io import atomic_write_text
except ImportError:
    from scripts.atomic_io import atomic_write_text


def write_gzip_ndjson(path, rows):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as fh:
        for item in rows:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--of", type=int, default=4)
    args = ap.parse_args()
    out = ROOT / "taxonomy" / "snapshots" / args.date
    summaries = []
    products = {}
    rankings = []
    for shard in range(args.of):
        summary_path = out / f"summary.shard-{shard}.json"
        if not summary_path.exists():
            raise SystemExit(f"summary eksik: shard-{shard}")
        summaries.append(json.loads(summary_path.read_text()))
        for prefix, target in [("products", products), ("rankings", rankings)]:
            file = out / f"{prefix}.shard-{shard}.ndjson.gz"
            if not file.exists():
                raise SystemExit(f"çıktı eksik: {file}")
            with gzip.open(file, "rt", encoding="utf-8") as fh:
                for line in fh:
                    item = json.loads(line)
                    if prefix == "products":
                        key = item.get("product_key") or item.get("product_id") or item.get("url")
                        if key:
                            target[key] = item
                    else:
                        target.append(item)
    summary_dates = {s.get("date") for s in summaries}
    root_ids = {root.get("root_id") for s in summaries for root in s.get("roots", []) if root.get("root_id")}
    all_roots_pass = all(s.get("status") == "PASS" for s in summaries)
    valid_run = summary_dates == {args.date} and len(root_ids) >= EXPECTED_ROOT_COUNT and all_roots_pass
    final_summary = {
        "marketplace": "hepsiburada", "date": args.date, "status": "PASS" if all(s.get("status") == "PASS" for s in summaries) else "INSUFFICIENT_SOURCE",
        "shards": summaries, "productCount": len(products), "rankingCount": len(rankings),
        "rootCount": len(root_ids), "expectedRootCount": EXPECTED_ROOT_COUNT,
        "dateConsistent": summary_dates == {args.date}, "allRootsPass": all_roots_pass,
    }
    final_summary["status"] = "PASS" if valid_run else "INSUFFICIENT_SOURCE"
    write_gzip_ndjson(out / "products.ndjson.gz", products.values())
    write_gzip_ndjson(out / "rankings.ndjson.gz", rankings)
    atomic_write_text(out / "summary.json", json.dumps(final_summary, ensure_ascii=False, indent=2))
    print(f"TAXCOLLECT_MERGE_{final_summary['status']} products={len(products)} rankings={len(rankings)}")
    return 0 if final_summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
