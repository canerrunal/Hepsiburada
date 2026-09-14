#!/usr/bin/env python3
"""Hepsiburada detay turu (Playwright headed Chromium).

latest.json'daki her urun icin detay sayfasina gider:
- /api/v1/product/listings/<sku> (satici, fiyat, min fiyatlar, stok/depo, kampanya)
- /api/v1/otherMerchants (tum saticilar)
- DOM: puan, degerlendirme/yorum/soru sayilari, teslimat sinyalleri

Cikti: data/latest.detailed.json + data/history.csv'ye gunluk satirlar +
quality/latest.json'a detailCoverage. Kaldigi yerden devam eder (resume).

Kullanim: python3 scripts/hb_detail_pw.py --profile elektronik [--limit 5]
"""
import argparse
import csv
import datetime
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")


def out_root_for(profile):
    if profile == "elektronik":
        return ROOT
    return ROOT / "categories" / profile


DOM_JS = """() => {
  const b = document.body ? document.body.innerText : '';
  const find = (re) => (b.match(re) || []).slice(0, 6);
  return {
    reviewNums: find(/(\\d[\\d.]*)\\s*(değerlendirme|yorum)/gi),
    questionNums: find(/(\\d[\\d.]*)\\s*soru/gi),
    stockText: find(/(Stokta.{0,30}|Son.{0,25}ürün|Tükendi|Stok.{0,20}kalmedi)/gi),
    delivery: find(/(Yarın kapında|hızlı teslimat|kargo bedava|kargoda)/gi),
    sellerShown: find(/(Satıcı\\s*:\\s*.{0,40})/gi),
  };
}"""


def parse_int_tr(s):
    try:
        return int(str(s).replace(".", "").split()[0])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="elektronik")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    args = ap.parse_args()

    out_root = out_root_for(args.profile)
    latest_path = out_root / "data" / "latest.json"
    if not latest_path.exists():
        print(f"latest.json yok: {latest_path}", file=sys.stderr)
        return 1
    latest = json.loads(latest_path.read_text())
    products = latest.get("products", [])
    if args.limit:
        products = products[: args.limit]

    main_det_path = out_root / "data" / "latest.detailed.json"
    det_path = main_det_path if args.of == 1 else out_root / "data" / f"latest.detailed.shard-{args.shard}.json"
    done = {}
    for cand in ([main_det_path] if args.of == 1 else [main_det_path, det_path]):
        if cand.exists():
            try:
                prev = json.loads(cand.read_text())
                if prev.get("date") == latest.get("date"):
                    for pr in prev.get("products", []):
                        if pr.get("detail_ok"):
                            done[pr.get("sku") or pr.get("url")] = pr
            except Exception:
                pass

    todo = [pr for pr in products if (pr.get("sku") or pr.get("url")) not in done]
    if args.of > 1:
        todo = [pr for i, pr in enumerate(todo) if i % args.of == args.shard]
    print(f"DETAIL_START profile={args.profile} shard={args.shard}/{args.of} todo={len(todo)}/{len(products)}")
    if not todo:
        print("DETAIL_SKIP hepsi tamam")
        return 0

    from playwright.sync_api import sync_playwright

    enriched = 0
    failed = 0
    consecutive_blocks = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(locale="tr-TR", user_agent=UA, viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        captured = {}

        def on_response(r):
            try:
                if "product/listings" in r.url:
                    captured["listings"] = r.json()
                elif "otherMerchants" in r.url:
                    captured["merchants"] = r.json()
            except Exception:
                pass

        page.on("response", on_response)
        for pr in todo:
            url = pr.get("url") or ""
            if not url:
                failed += 1
                continue
            captured.clear()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1500)
                if "Güvenlik" in (page.title() or ""):
                    raise RuntimeError("guvenlik-engeli")
                dom = page.evaluate(DOM_JS)
                listings = (captured.get("listings") or {}).get("data", {}).get("listings", [])
                merch_data = ((captured.get("merchants") or {}).get("data", {}).get("result", {}) or {})
                others = merch_data.get("otherMerchants", []) or []
                winner = listings[0] if listings else {}
                wprice = (winner.get("price") or {})
                sellers = [{"merchant": (l.get("merchantName") or ""), "price": ((l.get("price") or {}).get("value")),
                            "listing_id": l.get("listingId") or ""} for l in listings]
                for o in others:
                    if o.get("merchantName") not in [s["merchant"] for s in sellers]:
                        sellers.append({"merchant": o.get("merchantName") or "",
                                        "price": ((o.get("priceData") or {}).get("discountedPrice")
                                                  or (o.get("priceData") or {}).get("price")),
                                        "listing_id": o.get("listingId") or ""})
                mins = {m.get("name"): m.get("value") for m in (winner.get("minimumPrices") or [])}
                revs = [parse_int_tr(x.split()[0]) for x in (dom.get("reviewNums") or [])]
                ques = [parse_int_tr(x.split()[0]) for x in (dom.get("questionNums") or [])]
                pr["detail"] = {
                    "listings_count": len(listings),
                    "sellers_count": len(sellers),
                    "sellers": sellers[:20],
                    "winner_merchant": winner.get("merchantName") or "",
                    "winner_price": wprice.get("value"),
                    "minimum_price_10d": mins.get("10"),
                    "minimum_price_30d": mins.get("30"),
                    "fast_shipping": bool(winner.get("fastShipping", False)),
                    "is_salable": winner.get("isSalable", True),
                    "campaign_count": len(winner.get("campaignIds") or []),
                    "other_merchants_count": len(others),
                    "rating": pr.get("rating"),
                    "review_count": (revs[0] if revs else pr.get("review_count")),
                    "question_count": (ques[0] if ques else None),
                    "delivery_signals": (dom.get("delivery") or [])[:6],
                    "stock_text": (dom.get("stockText") or [])[:3],
                }
                pr["detail_observed_at"] = stamp()
                pr["detail_ok"] = True
                enriched += 1
                consecutive_blocks = 0
            except Exception as e:
                pr["detail_ok"] = False
                pr["detail_error"] = str(e)[:80]
                failed += 1
                if "guvenlik" in str(e):
                    consecutive_blocks += 1
                    print(f"DETAIL_BLOCK {consecutive_blocks}/3 url={url[:80]}", flush=True)
                    if consecutive_blocks >= 3:
                        print("DETAIL_BLOCK ust uste 3 engel, duruluyor", flush=True)
                        done[pr.get("sku") or pr.get("url")] = pr
                        break
            done[pr.get("sku") or pr.get("url")] = pr
            if (enriched + failed) % 25 == 0:
                merged_ck = [done.get(p.get("sku") or p.get("url"), p) for p in products]
                det_path.write_text(json.dumps(
                    {"profile": args.profile, "date": latest.get("date"), "collectedAt": latest.get("collectedAt"),
                     "detailRunAt": stamp(), "count": len(merged_ck), "products": merged_ck},
                    ensure_ascii=False, indent=2))
                print(f"CHECKPOINT enriched={enriched} failed={failed}", flush=True)
            time.sleep(1.5)
        browser.close()

    # Siralamayi koru: latest'teki tum urunler, detaylananlar guncel
    merged = []
    for pr in products:
        key = pr.get("sku") or pr.get("url")
        merged.append(done.get(key, pr))
    out = {"profile": args.profile, "date": latest.get("date"), "collectedAt": latest.get("collectedAt"),
           "detailRunAt": stamp(), "count": len(merged), "products": merged}
    det_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    if args.of > 1:
        print(f"DETAIL_SHARD_OK profile={args.profile} shard={args.shard} enriched={enriched} failed={failed}")
        return 0 if enriched else 2

    # history.csv'ye gunluk satirlar (ayni gun+sku varsa tekrar yazma)
    hist_path = out_root / "data" / "history.csv"
    existing_keys = set()
    if hist_path.exists():
        with open(hist_path, newline="") as f:
            for row in csv.DictReader(f):
                existing_keys.add((row.get("date"), row.get("sku")))
    new_file = not hist_path.exists()
    ok_det = [m for m in merged if m.get("detail_ok")]
    with open(hist_path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "sku", "brand", "title", "price", "winner_merchant", "sellers_count",
                        "rating", "review_count", "question_count", "minimum_price_30d", "url"])
        for m in merged:
            if (out["date"], m.get("sku")) in existing_keys:
                continue
            d = m.get("detail") or {}
            w.writerow([out["date"], m.get("sku"), m.get("brand"), m.get("title"), m.get("price"),
                        d.get("winner_merchant", m.get("merchant")), d.get("sellers_count", 1),
                        d.get("rating", m.get("rating")), d.get("review_count", m.get("review_count")),
                        d.get("question_count"), d.get("minimum_price_30d"), m.get("url")])

    # quality'ye detay kapsama
    qpath = out_root / "quality" / "latest.json"
    q = json.loads(qpath.read_text()) if qpath.exists() else {}
    fields = ["winner_merchant", "sellers_count", "review_count", "question_count", "minimum_price_30d"]
    cov = {}
    for fl in fields:
        cov[fl] = round(100.0 * sum(1 for m in ok_det if (m.get("detail") or {}).get(fl) not in (None, "", 0)) / max(len(ok_det), 1), 1)
    q["detailAttempted"] = len(todo)
    q["detailRefreshed"] = enriched
    q["detailFailed"] = failed
    q["detailSuccessRate"] = round(100.0 * enriched / max(len(todo), 1), 1)
    q["detailCoverage"] = cov
    qpath.write_text(json.dumps(q, ensure_ascii=False, indent=2))
    print(f"DETAIL_OK profile={args.profile} enriched={enriched} failed={failed} cov={cov}")
    return 0 if enriched else 2


if __name__ == "__main__":
    sys.exit(main())
