#!/usr/bin/env python3
"""Hepsiburada kategori agaci BFS crawler (Playwright Chromium).

Cikti: taxonomy/catalog.json, taxonomy/catalog.csv + resume state
taxonomy/crawl-state.json. Kaldigi yerden devam eder.

Kullanim: python3 scripts/hb_taxonomy_crawl.py [--max-pages 5000]
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
from collections import deque
from pathlib import Path

try:
    from hb_playwright_config import add_browser_mode_args
except ImportError:
    from scripts.hb_playwright_config import add_browser_mode_args
from urllib.parse import urlparse

try:
    from atomic_io import atomic_write_text
except ImportError:
    from scripts.atomic_io import atomic_write_text

ROOT = Path(__file__).resolve().parent.parent
TAX = ROOT / "taxonomy"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SEEDS = [
    ("Elektronik", "https://www.hepsiburada.com/ev-elektronik-urunleri-c-2147483638"),
    ("Moda", "https://www.hepsiburada.com/giyim-ayakkabi-c-2147483636"),
    ("Ev, Yasam, Kirtasiye, Ofis", "https://www.hepsiburada.com/ev-dekorasyon-c-60002028"),
    ("Oto, Bahce, Yapi Market", "https://www.hepsiburada.com/yapi-market-bahce-oto-c-60002705"),
    ("Anne, Bebek, Oyuncak", "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639"),
    ("Spor, Outdoor", "https://www.hepsiburada.com/spor-outdoor-urunleri-c-60001546"),
    ("Kozmetik, Kisisel Bakim", "https://www.hepsiburada.com/kozmetik-kisisel-bakim-urunleri-c-60001547"),
    ("Supermarket, Pet Shop", "https://www.hepsiburada.com/supermarket-c-2147483619"),
    ("Kitap, Muzik, Film, Hobi", "https://www.hepsiburada.com/kitaplar-filmler-muzikler-c-60001501"),
]
CAT_RE = re.compile(r"^/([a-z0-9][a-z0-9\-]*)-c-(\d+)/?$")
SKIP_SEG = ("uyelik",)


def canon(href):
    try:
        u = urlparse(href if href.startswith("http") else "https://www.hepsiburada.com" + href)
        if "hepsiburada.com" not in (u.hostname or ""):
            return None
        path = u.path.rstrip("/")
        if path.count("/") != 1:
            return None
        m = CAT_RE.match(path + "/")
        if not m:
            return None
        slug, cid = m.group(1), m.group(2)
        if slug in SKIP_SEG:
            return None
        return cid, f"https://www.hepsiburada.com{path}"
    except Exception:
        return None


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")


def goto_with_retry(page, url, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return
        except Exception as error:
            last_error = error
            if "guvenlik" in str(error).lower():
                raise
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise last_error


def _legacy_save(*a, **k):
    raise RuntimeError("save_now kullan")


def save(cats, queued, visited_count):  # geriye uyumluluk; kullanilmiyor
    _legacy_save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=5000)
    ap.add_argument("--seeds", default="all")
    ap.add_argument("--tag", default="")
    add_browser_mode_args(ap)
    args = ap.parse_args()
    TAX.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.tag}" if args.tag else ""
    state_path = TAX / f"crawl-state{suffix}.json"
    catalog_path = TAX / f"catalog{suffix}.json"
    csv_path = TAX / f"catalog{suffix}.csv"
    if args.seeds == "all":
        my_seeds = list(range(len(SEEDS)))
    else:
        my_seeds = [int(x) for x in args.seeds.split(",")]

    cats, queue, visited = {}, deque(), set()
    poison = set()
    # Tohumlar bastan seviye-1 kayitli (yanlis ebeveyn onler)
    for name, url in SEEDS:
        cid = url.rsplit("-c-", 1)[1]
        cats[cid] = {"id": cid, "parent_id": "", "name": name, "url": url, "level": 1, "path": name,
                     "path_ids": [cid], "root_id": cid, "root_name": name}
    if state_path.exists():
        try:
            s = json.loads(state_path.read_text())
            if s.get("date") == today():
                for cid, parent, name, url, level, path in s.get("queued", []):
                    queue.append((cid, parent, name, url, level, path))
                poison.update(s.get("poison", []))
        except Exception:
            pass
    if catalog_path.exists():
        try:
            old = json.loads(catalog_path.read_text())
            if old.get("date") == today():
                for r in old.get("categories", []):
                    if r["id"] not in cats or r["level"] < cats[r["id"]]["level"]:
                        cats[r["id"]] = r
        except Exception:
            pass
    if not queue:
        for i in my_seeds:
            name, url = SEEDS[i]
            cid = url.rsplit("-c-", 1)[1]
            queue.append((cid, "", name, url, 1, name))
    visited.update([r["id"] for r in cats.values() if r["level"] == 1 and r["id"] not in [SEEDS[i][1].rsplit("-c-", 1)[1] for i in my_seeds]])
    # Not: sadece kendi tohumlarim islenecek; diger tohum id'leri kesifte gorulurse
    # catalog'da seviye-1 durur, kuyruga eklenmez (asagida visited kontrolu).
    def save_now():
        child_counts = {}
        for row in cats.values():
            parent_id = row.get("parent_id")
            if parent_id:
                child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
        for row in cats.values():
            path_ids = row.get("path_ids") or [row["id"]]
            row.update({
                "full_path": row.get("path") or row.get("name"),
                "path_ids": path_ids,
                "path_slug": row.get("url", "").rstrip("/").rsplit("/", 1)[-1],
                "root_id": row.get("root_id") or path_ids[0],
                "root_name": row.get("root_name") or row.get("name"),
                "has_children": child_counts.get(row["id"], 0) > 0,
                "child_count": child_counts.get(row["id"], 0),
                "source_url": row.get("url"),
                "discovered_at": row.get("discovered_at") or stamp(),
                "is_active": True,
            })
        rows = sorted(cats.values(), key=lambda r: (r["level"], r["path"]))
        atomic_write_text(catalog_path, json.dumps(
            {"date": today(), "status": "LIVE-CRAWL", "count": len(rows), "categories": rows},
            ensure_ascii=False, indent=2))
        with open(csv_path.with_suffix(csv_path.suffix + ".tmp"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "parent_id", "name", "url", "level", "path", "root_id", "root_name",
                        "full_path", "path_ids", "path_slug", "has_children", "child_count", "source_url",
                        "discovered_at", "is_active"])
            for r in rows:
                w.writerow([r["id"], r["parent_id"], r["name"], r["url"], r["level"], r["path"],
                            r["root_id"], r["root_name"], r["full_path"], ">".join(r["path_ids"]),
                            r["path_slug"], r["has_children"], r["child_count"], r["source_url"],
                            r["discovered_at"], r["is_active"]])
        os.replace(csv_path.with_suffix(csv_path.suffix + ".tmp"), csv_path)
        atomic_write_text(state_path, json.dumps(
            {"date": today(), "queued": list(queue), "visited_count": len(visited),
             "poison": sorted(poison)}, ensure_ascii=False))

    from playwright.sync_api import sync_playwright
    pages_done, blocks = 0, 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = None
        try:
            ctx = browser.new_context(locale="tr-TR", user_agent=UA, viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            while queue and pages_done < args.max_pages:
                cid, parent, name, url, level, path = queue.popleft()
                if cid in visited or cid in poison:
                    continue
                visited.add(cid)
                try:
                    goto_with_retry(page, url)
                    page.wait_for_timeout(4000)
                    if "Güvenlik" in (page.title() or ""):
                        raise RuntimeError("guvenlik-engeli")
                    links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => ({text: (a.innerText||'').trim().slice(0,60), href: a.getAttribute('href')||''}))""")
                    blocks = 0
                    for l in links:
                        c = canon(l["href"])
                        if not c:
                            continue
                        nid, nurl = c
                        if nid not in cats:
                            nm = l["text"] if len(l["text"]) > 2 else nurl.rsplit("/", 1)[-1].rsplit("-c-", 1)[0].replace("-", " ")
                            parent_row = cats.get(cid, {})
                            parent_ids = parent_row.get("path_ids") or [cid]
                            parent_root = parent_row.get("root_id") or parent_ids[0]
                            parent_root_name = parent_row.get("root_name") or parent_row.get("name")
                            cats[nid] = {"id": nid, "parent_id": cid, "name": nm, "url": nurl,
                                         "level": level + 1, "path": f"{path} > {nm}",
                                         "path_ids": parent_ids + [nid], "root_id": parent_root,
                                         "root_name": parent_root_name, "discovered_at": stamp()}
                        if nid not in visited:
                            queue.append((nid, cid, cats[nid]["name"], nurl, level + 1, cats[nid]["path"]))
                    if cid not in cats:
                        cats[cid] = {"id": cid, "parent_id": parent, "name": name, "url": url,
                                     "level": level, "path": path, "path_ids": [cid],
                                     "root_id": cid, "root_name": name, "discovered_at": stamp()}
                    pages_done += 1
                    if pages_done % 20 == 0:
                        save_now()
                        print(f"CRAWL pages={pages_done} cats={len(cats)} queue={len(queue)}", flush=True)
                except Exception as e:
                    if "guvenlik" in str(e):
                        blocks += 1
                        print(f"CRAWL_BLOCK {blocks}/3 {url[:70]}", flush=True)
                        if blocks >= 2:
                            poison.add(cid)
                            blocks = 0
                            save_now()
                            time.sleep(10)
                            continue
                        visited.discard(cid)
                        queue.appendleft((cid, parent, name, url, level, path))
                        time.sleep(20)
                        continue
                print(f"CRAWL_ERR {str(e)[:60]} {url[:60]}", flush=True)
            time.sleep(float(os.environ.get("HB_CRAWL_DELAY", "2.5")))
        finally:
            if ctx is not None:
                ctx.close()
            browser.close()
    save_now()
    if not queue:
        final_catalog = json.loads(catalog_path.read_text())
        final_catalog["status"] = "COMPLETE"
        final_catalog["completed_at"] = stamp()
        atomic_write_text(catalog_path, json.dumps(final_catalog, ensure_ascii=False, indent=2))
    print(f"CRAWL_OK tag={args.tag or 'main'} pages={pages_done} cats={len(cats)} queue_left={len(queue)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
