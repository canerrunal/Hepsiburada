#!/usr/bin/env python3
"""Merge taxonomy product shards into one date-stamped snapshot."""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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
    final_summary = {
        "marketplace": "hepsiburada", "date": args.date, "status": "PASS" if all(s.get("status") == "PASS" for s in summaries) else "INSUFFICIENT_SOURCE",
        "shards": summaries, "productCount": len(products), "rankingCount": len(rankings),
        "rootCount": sum(len(s.get("roots", [])) for s in summaries),
    }
    with gzip.open(out / "products.ndjson.gz", "wt", encoding="utf-8") as fh:
        for item in products.values(): fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    with gzip.open(out / "rankings.ndjson.gz", "wt", encoding="utf-8") as fh:
        for item in rankings: fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(json.dumps(final_summary, ensure_ascii=False, indent=2))
    print(f"TAXCOLLECT_MERGE_{final_summary['status']} products={len(products)} rankings={len(rankings)}")
    return 0 if final_summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
