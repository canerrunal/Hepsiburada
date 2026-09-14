#!/usr/bin/env python3
"""Hepsiburada kategori agaci BFS crawler (Playwright headed Chromium).

Cikti: taxonomy/catalog.json, taxonomy/catalog.csv + resume state
taxonomy/crawl-state.json. Kaldigi yerden devam eder.

Kullanim: python3 scripts/hb_taxonomy_crawl.py [--max-pages 5000]
"""
import argparse
import csv
import datetime
import json
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

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


def _legacy_save(*a, **k):
    raise RuntimeError("save_now kullan")


def save(cats, queued, visited_count):  # geriye uyumluluk; kullanilmiyor
    _legacy_save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=5000)
    ap.add_argument("--seeds", default="all")
    ap.add_argument("--tag", default="")
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
        cats[cid] = {"id": cid, "parent_id": "", "name": name, "url": url, "level": 1, "path": name}
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
        rows = sorted(cats.values(), key=lambda r: (r["level"], r["path"]))
        catalog_path.write_text(json.dumps(
            {"date": today(), "status": "LIVE-CRAWL", "count": len(rows), "categories": rows},
            ensure_ascii=False, indent=2))
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "parent_id", "name", "url", "level", "path"])
            for r in rows:
                w.writerow([r["id"], r["parent_id"], r["name"], r["url"], r["level"], r["path"]])
        state_path.write_text(json.dumps(
            {"date": today(), "queued": list(queue), "visited_count": len(visited),
             "poison": sorted(poison)}, ensure_ascii=False))

    from playwright.sync_api import sync_playwright
    pages_done, blocks = 0, 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(locale="tr-TR", user_agent=UA, viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        while queue and pages_done < args.max_pages:
            cid, parent, name, url, level, path = queue.popleft()
            if cid in visited or cid in poison:
                continue
            visited.add(cid)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                if "Güvenlik" in (page.title() or ""):
                    raise RuntimeError("guvenlik-engeli")
                links = page.evaluate("""() => {
                  const out = [];
                  document.querySelectorAll('a[href]').forEach(a => {
                    const h = a.getAttribute('href') || '';
                    if (/-c-\\d+/.test(h)) out.push({text: (a.innerText||'').trim().slice(0,60), href: h});
                  });
                  return out;
                }""")
                blocks = 0
                for l in links:
                    c = canon(l["href"])
                    if not c:
                        continue
                    nid, nurl = c
                    if nid not in cats:
                        nm = l["text"] if l["text"] and len(l["text"]) > 2 else nurl.rsplit("/", 1)[-1].rsplit("-c-", 1)[0].replace("-", " ")
                        cats[nid] = {"id": nid, "parent_id": cid, "name": nm, "url": nurl,
                                     "level": level + 1, "path": f"{path} > {nm}"}
                    if nid not in visited:
                        queue.append((nid, cid, cats[nid]["name"], nurl, level + 1, cats[nid]["path"]))
                if cid not in cats:
                    slug = url.rsplit("/", 1)[-1].rsplit("-c-", 1)[0].replace("-", " ")
                    cats[cid] = {"id": cid, "parent_id": parent, "name": name or slug, "url": url,
                                 "level": level, "path": path}
                pages_done += 1
                if pages_done % 20 == 0:
                    save_now()
                    print(f"CRAWL pages={pages_done} cats={len(cats)} queue={len(queue)}", flush=True)
            except Exception as e:
                if "guvenlik" in str(e):
                    blocks += 1
                    print(f"CRAWL_BLOCK {blocks}/3 {url[:70]}", flush=True)
                    if blocks >= 2:
                        # Ayni URL ikinci kez engellendi: zehirli say, atla ve devam et
                        print(f"CRAWL_POISON atlandi {url[:70]}", flush=True)
                        poison.add(cid)
                        blocks = 0
                        save_now()
                        time.sleep(10)
                        continue
                    visited.discard(cid)
                    queue.appendleft((cid, parent, name, url, level, path))
                    if blocks >= 3:
                        print("CRAWL duruyor (ust uste engel), state kaydedildi", flush=True)
                        break
                    time.sleep(20)
                    continue
                print(f"CRAWL_ERR {str(e)[:60]} {url[:60]}", flush=True)
            time.sleep(2.5)
        browser.close()
    save_now()
    print(f"CRAWL_OK tag={args.tag or 'main'} pages={pages_done} cats={len(cats)} queue_left={len(queue)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
