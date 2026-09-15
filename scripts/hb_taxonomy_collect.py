#!/usr/bin/env python3
"""Collect ranked public products for taxonomy roots without fabricating data.

Each root is processed independently and can be sharded. Products are stored
once in products.ndjson.gz; category/rank membership is stored separately in
rankings.ndjson.gz.
"""
import argparse
import datetime
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAX = ROOT / "taxonomy"
EXPECTED_ROOT_COUNT = 9
ROOT_TARGET_POLICY = {
    "over_1000_subcategories": 4000,
    "500_to_999_subcategories": 2500,
    "under_500_subcategories": 2000,
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
STATE_JS = """() => {
  const vf = window.MORIA && window.MORIA.VERTICALFILTER ? Object.values(window.MORIA.VERTICALFILTER) : [];
  for (const v of vf) {
    try {
      const p = v && v.STATE && v.STATE.data && v.STATE.data.products;
      if (Array.isArray(p) && p.length) return p;
    } catch (e) {}
  }
  return [];
}"""


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")


def page_url(url, page):
    if page <= 1:
        return url
    return f"{url}{'&' if '?' in url else '?'}sayfa={page}"


def product_key(product):
    return product.get("product_key") or product.get("product_id") or product.get("canonical_url") or product.get("url") or product.get("sku")


def target_for_subcategory_count(subcategory_count, override=None):
    """Return the requested unique-product target for one root."""
    if override is not None:
        return int(override)
    if subcategory_count > 1000:
        return ROOT_TARGET_POLICY["over_1000_subcategories"]
    if subcategory_count >= 500:
        return ROOT_TARGET_POLICY["500_to_999_subcategories"]
    return ROOT_TARGET_POLICY["under_500_subcategories"]


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


def load_categories(allow_partial=False):
    file = TAX / "catalog.json"
    if not file.exists():
        raise SystemExit("taxonomy/catalog.json yok")
    data = json.loads(file.read_text())
    rows = data.get("categories", [])
    if not rows:
        raise SystemExit("taxonomy katalogu bos")
    status = str(data.get("status", "")).upper()
    by_id = {r.get("id"): r for r in rows if r.get("id")}
    roots = [r for r in rows if not r.get("parent_id") or r.get("parent_id") not in by_id]
    orphans = [r for r in rows if r.get("parent_id") and r.get("parent_id") not in by_id]
    invalid_roots = [r for r in roots if not r.get("id") or not (r.get("source_url") or r.get("url"))]
    if not allow_partial and status not in {"PASS", "COMPLETE"}:
        raise SystemExit(f"taxonomy katalogu hazir degil: status={status or 'UNKNOWN'}")
    if not allow_partial and len({r.get("id") for r in roots}) < EXPECTED_ROOT_COUNT:
        raise SystemExit(f"taxonomy kokleri eksik: {len(roots)}/{EXPECTED_ROOT_COUNT}")
    if not allow_partial and orphans:
        raise SystemExit(f"taxonomy parent'i bulunamayan kategori var: {len(orphans)}")
    if invalid_roots:
        raise SystemExit(f"taxonomy koklerinde kimlik veya URL eksik: {len(invalid_roots)}")

    children = {}
    for row in rows:
        parent_id = row.get("parent_id")
        if parent_id:
            children.setdefault(parent_id, []).append(row.get("id"))

    def lineage(category_id):
        chain = []
        seen = set()
        current = by_id.get(category_id)
        while current and current.get("id") not in seen:
            seen.add(current.get("id"))
            chain.append(current)
            current = by_id.get(current.get("parent_id")) if current.get("parent_id") else None
        chain.reverse()
        return chain

    normalized = []
    for original in rows:
        row = dict(original)
        chain = lineage(row.get("id"))
        root = chain[0] if chain else row
        row["root_id"] = root.get("id")
        row["root_name"] = root.get("name")
        row["path_ids"] = [item.get("id") for item in chain]
        row["canonical_path"] = " > ".join(item.get("name", "") for item in chain)
        row["full_path"] = row["canonical_path"]
        row["has_children"] = bool(children.get(row.get("id")))
        row["child_count"] = len(children.get(row.get("id"), []))
        row["source_url"] = row.get("source_url") or row.get("url")
        normalized.append(row)
    return data, normalized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-id", action="append", help="Sadece bu root ID; tekrarlanabilir")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--max-products", type=int, default=None, help="Tum kokler icin manuel hedef; varsayilan dinamik politika")
    ap.add_argument("--max-pages-per-category", type=int, default=100)
    ap.add_argument("--request-delay-ms", type=int, default=1500)
    ap.add_argument("--allow-partial", action="store_true", help="Sadece tanı için eksik katalogla devam et")
    try:
        from hb_playwright_config import add_browser_mode_args
    except ImportError:
        from scripts.hb_playwright_config import add_browser_mode_args
    add_browser_mode_args(ap)
    args = ap.parse_args()
    catalog, rows = load_categories(args.allow_partial)
    roots = [r for r in rows if int(r.get("level", 0)) == 1]
    if args.root_id:
        roots = [r for r in roots if r.get("id") in args.root_id]
    elif args.of > 1:
        roots = [r for i, r in enumerate(roots) if i % args.of == args.shard]
    date = today()
    out_dir = TAX / "snapshots" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"marketplace": "hepsiburada", "date": date,
               "catalogDate": catalog.get("date"), "catalogStatus": catalog.get("status"),
               "catalogRootCount": len([r for r in rows if int(r.get("level", 0)) == 1]),
               "targetPolicy": ROOT_TARGET_POLICY, "roots": [], "shard": args.shard, "of": args.of}
    products_out = []
    rankings_out = []

    from playwright.sync_api import sync_playwright
    from hb_collect_pw import extract_products, norm_product

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, args=["--disable-blink-features=AutomationControlled"])
        context = None
        try:
            context = browser.new_context(locale="tr-TR", user_agent=UA, viewport={"width": 1366, "height": 900})
            page = context.new_page()
            for root in roots:
                descendants = [r for r in rows if r.get("root_id") == root.get("id") or r.get("id") == root.get("id")]
                if not descendants:
                    descendants = [root]
                subcategory_count = max(len(descendants) - 1, 0)
                target = target_for_subcategory_count(subcategory_count, args.max_products)
                unique = {}
                membership = []
                errors = []
                category_rank = 0
                for category in descendants:
                    if len(unique) >= target:
                        break
                    stagnant = 0
                    for page_no in range(1, args.max_pages_per_category + 1):
                        if len(unique) >= target:
                            break
                        try:
                            goto_with_retry(page, page_url(category.get("source_url") or category.get("url") or "", page_no))
                            page.wait_for_timeout(4000)
                            if "Güvenlik" in (page.title() or ""):
                                raise RuntimeError("guvenlik-engeli")
                            raw = extract_products(page)
                            if not raw:
                                stagnant += 1
                                if stagnant >= 2:
                                    break
                                continue
                            added = 0
                            for pos, item in enumerate(raw, 1):
                                for product in norm_product(item, category.get("id"), pos, page_no, None):
                                    key = product_key(product)
                                    if not key:
                                        continue
                                    if key not in unique:
                                        category_rank += 1
                                        product.update({
                                            "category_id": category.get("id"),
                                            "category_name": category.get("name"),
                                            "category_path": category.get("canonical_path") or category.get("full_path") or category.get("path"),
                                            "root_category_id": root.get("id"),
                                            "root_category_name": root.get("name"),
                                            "source_segment": "taxonomy",
                                            "source_page": page_no,
                                            "rank_scope": "category",
                                        })
                                        unique[key] = product
                                        products_out.append(product)
                                        added += 1
                                    membership.append({"category_id": category.get("id"), "category_path": category.get("full_path") or category.get("path"),
                                                       "product_key": key, "rank": category_rank, "source": category.get("source_url") or category.get("url"),
                                                       "source_page": page_no, "observed_date": date, "captured_at": stamp()})
                                    if len(unique) >= target:
                                        break
                                if len(unique) >= target:
                                    break
                            stagnant = 0 if added else stagnant + 1
                            if stagnant >= 2:
                                break
                            time.sleep(args.request_delay_ms / 1000)
                        except Exception as error:
                            errors.append({"category_id": category.get("id"), "url": category.get("source_url") or category.get("url"), "error": str(error)[:120]})
                            break
                rankings_out.extend(membership)
                status = "PASS" if len(unique) >= target else "INSUFFICIENT_SOURCE"
                summary["roots"].append({"root_id": root.get("id"), "root_name": root.get("name"),
                                         "subcategory_count": subcategory_count, "category_count": len(descendants),
                                         "unique_product_count": len(unique), "target": target,
                                         "target_basis": "subcategory_count_excluding_root",
                                         "status": status, "error_count": len(errors),
                                         "errors": errors[:20]})
        finally:
            if context is not None:
                context.close()
            browser.close()

    suffix = f".shard-{args.shard}" if args.of > 1 else ""
    products_file = out_dir / f"products{suffix}.ndjson.gz"
    rankings_file = out_dir / f"rankings{suffix}.ndjson.gz"
    with gzip.open(products_file, "wt", encoding="utf-8") as f:
        for item in products_out:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with gzip.open(rankings_file, "wt", encoding="utf-8") as f:
        for item in rankings_out:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary["productCount"] = len(products_out)
    summary["rankingCount"] = len(rankings_out)
    summary["status"] = "PASS" if summary["roots"] and all(r["status"] == "PASS" for r in summary["roots"]) else "INSUFFICIENT_SOURCE"
    (out_dir / f"summary.shard-{args.shard}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"TAXCOLLECT_{summary['status']} shard={args.shard}/{args.of} products={len(products_out)} roots={len(summary['roots'])}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
