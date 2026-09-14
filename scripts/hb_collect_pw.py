#!/usr/bin/env python3
"""Hepsiburada pilot profil toplayici (Playwright headed Chromium).

Trendyol mimarisiyle ayni cikti semasi:
categories/<profil>/data/latest.json|csv, snapshots/<tarih>/, lists/<tarih>/,
reports/<tarih>.md|latest.md|telegram-latest.txt, quality/latest.json

Kullanim: python3 scripts/hb_collect_pw.py --profile elektronik [--max-products 300]
"""
import argparse
import csv
import datetime
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATE_JS = """() => {
  const vf = window.MORIA && window.MORIA.VERTICALFILTER ? Object.values(window.MORIA.VERTICALFILTER) : [];
  for (const v of vf) {
    try {
      const prods = v && v.STATE && v.STATE.data && v.STATE.data.products;
      if (Array.isArray(prods) && prods.length) return prods;
    } catch (e) {}
  }
  return [];
}"""

ABS = "https://www.hepsiburada.com"


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")


def with_page(url, seg_name, n):
    if "sayfa=" in url:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}sayfa={n}" if n > 1 else url


def extract_products(page):
    try:
        return page.evaluate(STATE_JS) or []
    except Exception:
        return []


def norm_product(raw, seg_name, seg_pos, page_no):
    variants = raw.get("variantList") or []
    out = []
    for v in variants:
        listing = v.get("listing") or {}
        price_info = listing.get("priceInfo") or {}
        sku = v.get("sku") or ""
        url = v.get("url") or ""
        if url.startswith("/"):
            url = ABS + url
        out.append({
            "sku": sku,
            "product_id": raw.get("productId") or "",
            "brand": raw.get("brand") or "",
            "title": v.get("name") or "",
            "url": url,
            "price": price_info.get("price"),
            "original_price": price_info.get("originalPrice"),
            "discount_rate": price_info.get("discountRate"),
            "merchant": listing.get("merchantName") or "",
            "merchant_id": listing.get("merchantId") or "",
            "listing_id": listing.get("listingId") or "",
            "minimum_price": listing.get("minimumPrice"),
            "in_stock": bool(v.get("procurable", True)),
            "rating": raw.get("customerReviewRating"),
            "review_count": raw.get("customerReviewCount"),
            "image": ((v.get("images") or [{}])[0].get("link") or ""),
            "main_category": ((raw.get("mainCategory") or {}).get("name") or ""),
            "source_segment": seg_name,
            "segment_position": seg_pos,
            "source_page": page_no,
        })
    if not out:
        url = ""
        out.append({
            "sku": "", "product_id": raw.get("productId") or "", "brand": raw.get("brand") or "",
            "title": "", "url": url, "price": None, "source_segment": seg_name,
            "segment_position": seg_pos, "source_page": page_no,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="elektronik")
    ap.add_argument("--max-products", type=int, default=None)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    cfg_path = ROOT / ("config.json" if args.profile == "elektronik" and (ROOT / "config.json").exists() else f"profiles/{args.profile}.json")
    if args.profile != "elektronik" or not cfg_path.exists():
        cfg_path = ROOT / "profiles" / f"{args.profile}.json"
    if not cfg_path.exists():
        print(f"Profil ayari bulunamadi: {cfg_path}", file=sys.stderr)
        return 1
    cfg = json.loads(cfg_path.read_text())
    max_products = args.max_products or cfg.get("maxProducts", 300)
    minimum = cfg.get("minimumProducts", 200)
    delay = (cfg.get("requestDelayMs", 1500) / 1000.0) + 1.0

    out_root = ROOT if (args.profile == "elektronik" and cfg_path.name == "config.json") else (ROOT / "categories" / args.profile)
    date = today()
    collected_at = stamp()
    for d in ["data", f"snapshots/{date}", f"lists/{date}", "reports", "quality"]:
        (out_root / d).mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    seen = set()
    products = []
    block_error = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="tr-TR",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        for seg in cfg.get("searchSegments", []):
            seg_name = seg.get("name", "?")
            page_no = 0
            stagnant = 0
            while len(products) < max_products and page_no < (cfg.get("maxPagesPerSegment", 20)):
                page_no += 1
                url = with_page(seg.get("url", ""), seg_name, page_no)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(6000)
                    if "Güvenlik" in (page.title() or ""):
                        raise RuntimeError("guvenlik-engeli")
                    raw_list = extract_products(page)
                    if not raw_list:
                        stagnant += 1
                        if stagnant >= 3:
                            break
                        time.sleep(delay)
                        continue
                    added = 0
                    pos = 0
                    for raw in raw_list:
                        pos += 1
                        for prod in norm_product(raw, seg_name, pos, page_no):
                            key = prod.get("sku") or prod.get("url")
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            prod["rank"] = len(products) + 1
                            products.append(prod)
                            added += 1
                            if len(products) >= max_products:
                                break
                        if len(products) >= max_products:
                            break
                    if added == 0:
                        stagnant += 1
                        if stagnant >= 3:
                            break
                    else:
                        stagnant = 0
                except Exception as e:
                    block_error = block_error or str(e)[:80]
                    break
                time.sleep(delay)
            if len(products) >= max_products:
                break
        browser.close()

    passed = len(products) >= minimum
    latest = {"profile": args.profile, "date": date, "collectedAt": collected_at,
              "source": cfg.get("sourceLabel", ""), "count": len(products), "products": products}
    (out_root / "data" / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2))
    (out_root / "snapshots" / date / "products.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2))
    with open(out_root / "data" / "latest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "sku", "brand", "title", "price", "original_price", "merchant", "rating", "review_count", "url", "source_segment"])
        for pr in products:
            w.writerow([pr.get("rank"), pr.get("sku"), pr.get("brand"), pr.get("title"), pr.get("price"),
                        pr.get("original_price"), pr.get("merchant"), pr.get("rating"), pr.get("review_count"),
                        pr.get("url"), pr.get("source_segment")])
    import shutil
    shutil.copy(out_root / "data" / "latest.csv", out_root / "lists" / date / "trending.csv")
    md = (f"# {cfg.get('reportTitle', args.profile)} — {date}\n\n"
          f"> Kaynak: {cfg.get('sourceLabel', '')}\n> Toplama: {collected_at}\n"
          f"> Havuz: {len(products)} ürün | Kalite: **{'PASS' if passed else 'FAIL'}**\n"
          + (f"> Not: kisit ({block_error}).\n" if block_error else ""))
    (out_root / "reports" / f"{date}.md").write_text(md)
    (out_root / "reports" / "latest.md").write_text(md)
    (out_root / "reports" / "telegram-latest.txt").write_text(
        f"{cfg.get('telegramTitle', args.profile)} {date}: {len(products)} ürün, kalite {'PASS' if passed else 'FAIL'}.")
    quality = {"status": "PASS" if passed else "FAIL", "productCount": len(products),
               "minimumProducts": minimum, "date": date, "generatedAt": collected_at, "blockError": block_error}
    (out_root / "quality" / "latest.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2))
    print(f"COLLECT_{'OK' if passed else 'FAIL'} profile={args.profile} count={len(products)}" + (f" block={block_error}" if block_error else ""))
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
