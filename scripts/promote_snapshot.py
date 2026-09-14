#!/usr/bin/env python3
"""Atomically promote a quality-passing candidate snapshot to latest."""
import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    out = ROOT if args.profile == "elektronik" else ROOT / "categories" / args.profile
    candidate = out / "data" / "latest.candidate.json"
    if not candidate.exists():
        raise SystemExit(f"candidate yok: {candidate}")
    target = out / "data" / "latest.json"
    tmp = target.with_suffix(".json.tmp")
    shutil.copyfile(candidate, tmp)
    os.replace(tmp, target)
    detailed_candidate = out / "data" / "latest.detailed.candidate.json"
    detailed_target = out / "data" / "latest.detailed.json"
    if detailed_candidate.exists():
        shutil.copyfile(detailed_candidate, detailed_target)
    history_candidate = out / "data" / "history.candidate.csv"
    history_target = out / "data" / "history.csv"
    if history_candidate.exists():
        import csv
        existing = set()
        if history_target.exists():
            with history_target.open(newline="") as fh:
                existing = {(r.get("date"), r.get("sku")) for r in csv.DictReader(fh)}
        rows = list(csv.reader(history_candidate.open(newline="")))
        if rows:
            write_header = not history_target.exists() or history_target.stat().st_size == 0
            with history_target.open("a", newline="") as fh:
                writer = csv.writer(fh)
                if write_header:
                    writer.writerow(rows[0])
                for row in rows[1:]:
                    if len(row) >= 2 and (row[0], row[1]) not in existing:
                        writer.writerow(row)
    for src_name, dst_name in [
        ("latest.candidate.csv", "latest.csv"),
        ("telegram-candidate.txt", "telegram-latest.txt"),
    ]:
        src = out / "data" / src_name if src_name.endswith(".csv") else out / "reports" / src_name
        dst = out / "data" / dst_name if dst_name.endswith(".csv") else out / "reports" / dst_name
        if src.exists():
            shutil.copyfile(src, dst)
    date = __import__("json").loads(candidate.read_text()).get("date")
    snap = out / "snapshots" / date
    snap.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(candidate, snap / "products.json")
    cand_report = out / "reports" / f"{date}.candidate.md"
    if cand_report.exists():
        shutil.copyfile(cand_report, out / "reports" / f"{date}.md")
        shutil.copyfile(cand_report, out / "reports" / "latest.md")
    cand_list = out / "lists" / date / "trending.candidate.csv"
    if cand_list.exists():
        shutil.copyfile(cand_list, out / "lists" / date / "trending.csv")
    print(f"PROMOTE_OK profile={args.profile} date={date}")


if __name__ == "__main__":
    main()
