#!/usr/bin/env python3
"""Parcali kataloglari birlestir: catalog.json + catalog.csv.

Kullanim: python3 scripts/hb_taxonomy_merge.py --tags a,b
"""
import argparse
import csv
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAX = ROOT / "taxonomy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="a,b")
    args = ap.parse_args()
    merged = {}
    for tag in args.tags.split(","):
        p = TAX / f"catalog-{tag}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        for r in d.get("categories", []):
            old = merged.get(r["id"])
            if old is None or (r["level"], len(r["path"])) < (old["level"], len(old["path"])):
                merged[r["id"]] = r
    date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")
    rows = sorted(merged.values(), key=lambda r: (r["level"], r["path"]))
    (TAX / "catalog.json").write_text(json.dumps(
        {"date": date, "status": "LIVE-CRAWL", "count": len(rows), "categories": rows},
        ensure_ascii=False, indent=2))
    with open(TAX / "catalog.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "parent_id", "name", "url", "level", "path"])
        for r in rows:
            w.writerow([r["id"], r["parent_id"], r["name"], r["url"], r["level"], r["path"]])
    by_level = {}
    for r in rows:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
    print(f"TAXMERGE_OK count={len(rows)} levels={by_level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
