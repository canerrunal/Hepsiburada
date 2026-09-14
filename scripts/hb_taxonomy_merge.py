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


def write_status(status, reason, shards):
    TAX.mkdir(parents=True, exist_ok=True)
    (TAX / "status.json").write_text(json.dumps({
        "marketplace": "hepsiburada", "date": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d"),
        "status": status, "reason": reason, "shards": shards,
    }, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="a,b")
    args = ap.parse_args()
    merged = {}
    shards = {}
    for tag in args.tags.split(","):
        p = TAX / f"catalog-{tag}.json"
        if not p.exists():
            shards[tag] = {"status": "MISSING"}
            continue
        d = json.loads(p.read_text())
        state_path = TAX / f"crawl-state-{tag}.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        shards[tag] = {"status": d.get("status"), "count": d.get("count"), "queue": len(state.get("queued", []))}
        if d.get("status") != "COMPLETE" or state.get("queued"):
            write_status("IN_PROGRESS", f"shard {tag} tamamlanmadi", shards)
            print(f"TAXMERGE_WAIT shard={tag} status={d.get('status')} queue={len(state.get('queued', []))}")
            return 2
        for r in d.get("categories", []):
            old = merged.get(r["id"])
            if old is None or (r["level"], len(r["path"])) < (old["level"], len(old["path"])):
                merged[r["id"]] = r
    date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")
    rows = sorted(merged.values(), key=lambda r: (r["level"], r["path"]))
    for row in rows:
        row.setdefault("full_path", row.get("path"))
        row.setdefault("path_ids", [row["id"]])
        row.setdefault("path_slug", row.get("url", "").rstrip("/").rsplit("/", 1)[-1])
        row.setdefault("root_id", row["path_ids"][0])
        row.setdefault("root_name", row.get("name"))
        row.setdefault("has_children", False)
        row.setdefault("child_count", 0)
        row.setdefault("source_url", row.get("url"))
        row.setdefault("discovered_at", None)
        row.setdefault("is_active", True)
    (TAX / "catalog.json").write_text(json.dumps(
        {"marketplace": "hepsiburada", "date": date, "status": "PASS", "count": len(rows), "categories": rows},
        ensure_ascii=False, indent=2))
    with open(TAX / "catalog.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "parent_id", "name", "url", "level", "path", "root_id", "root_name",
                    "full_path", "path_ids", "path_slug", "has_children", "child_count", "source_url",
                    "discovered_at", "is_active"])
        for r in rows:
            w.writerow([r["id"], r["parent_id"], r["name"], r["url"], r["level"], r["path"],
                        r["root_id"], r["root_name"], r["full_path"], ">".join(r["path_ids"]),
                        r["path_slug"], r["has_children"], r["child_count"], r["source_url"],
                        r["discovered_at"], r["is_active"]])
    by_level = {}
    for r in rows:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
    write_status("PASS", "tum shard tamamlandi", shards)
    print(f"TAXMERGE_OK count={len(rows)} levels={by_level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
