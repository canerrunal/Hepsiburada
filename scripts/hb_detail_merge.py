#!/usr/bin/env python3
"""Shard detay dosyalarini birlestir: latest.detailed.json + history.csv + quality.

Kullanim: python3 scripts/hb_detail_merge.py --profile supermarket --of 2
"""
import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--of", type=int, default=1)
    args = ap.parse_args()

    out_root = ROOT if args.profile == "elektronik" else ROOT / "categories" / args.profile
    latest_path = out_root / "data" / "latest.candidate.json"
    if not latest_path.exists():
        latest_path = out_root / "data" / "latest.json"
    latest = json.loads(latest_path.read_text())
    products = latest.get("products", [])
    done = {}
    detailed_name = "latest.detailed.candidate.json" if latest_path.name == "latest.candidate.json" else "latest.detailed.json"
    cands = [out_root / "data" / "latest.detailed.json", out_root / "data" / detailed_name] + [
        out_root / "data" / f"latest.detailed.shard-{s}.json" for s in range(args.of)]
    for cand in cands:
        if not cand.exists():
            continue
        try:
            prev = json.loads(cand.read_text())
            if prev.get("date") != latest.get("date"):
                continue
            for pr in prev.get("products", []):
                if pr.get("detail_ok"):
                    done[pr.get("sku") or pr.get("url")] = pr
        except Exception:
            pass
    merged = [done.get(p.get("sku") or p.get("url"), p) for p in products]
    ok = [m for m in merged if m.get("detail_ok")]
    out = {"marketplace": "hepsiburada", "profile": args.profile, "date": latest.get("date"), "collectedAt": latest.get("collectedAt"),
           "detailRunAt": stamp(), "count": len(merged), "products": merged}
    (out_root / "data" / detailed_name).write_text(json.dumps(out, ensure_ascii=False, indent=2))

    hist_path = out_root / "data" / ("history.candidate.csv" if latest_path.name == "latest.candidate.json" else "history.csv")
    existing = set()
    if hist_path.exists():
        with open(hist_path, newline="") as f:
            for row in csv.DictReader(f):
                existing.add((row.get("date"), row.get("sku")))
    with open(hist_path, "a", newline="") as f:
        w = csv.writer(f)
        if not hist_path.exists() or hist_path.stat().st_size == 0:
            w.writerow(["date", "sku", "brand", "title", "price", "winner_merchant", "sellers_count",
                        "rating", "review_count", "question_count", "minimum_price_30d", "url"])
        added = 0
        for m in merged:
            if (out["date"], m.get("sku")) in existing:
                continue
            d = m.get("detail") or {}
            w.writerow([out["date"], m.get("sku"), m.get("brand"), m.get("title"), m.get("price"),
                        d.get("winner_merchant", m.get("merchant")), d.get("sellers_count", 1),
                        d.get("rating", m.get("rating")), d.get("review_count", m.get("review_count")),
                        d.get("question_count"), d.get("minimum_price_30d"), m.get("url")])
            added += 1

    qpath = out_root / "quality" / "latest.json"
    q = json.loads(qpath.read_text()) if qpath.exists() else {}
    fields = ["winner_merchant", "sellers_count", "review_count", "question_count", "minimum_price_30d"]
    cov = {fl: round(100.0 * sum(1 for m in ok if (m.get("detail") or {}).get(fl) not in (None, "", 0)) / max(len(ok), 1), 1)
           for fl in fields}
    q["detailAttempted"] = len(products)
    q["detailRefreshed"] = len(ok)
    q["detailFailed"] = len(products) - len(ok)
    q["detailSuccessRate"] = round(100.0 * len(ok) / max(len(products), 1), 1)
    q["detailCoverage"] = cov
    qpath.write_text(json.dumps(q, ensure_ascii=False, indent=2))
    print(f"MERGE_OK profile={args.profile} ok={len(ok)}/{len(products)} history_added={added} cov={cov}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
