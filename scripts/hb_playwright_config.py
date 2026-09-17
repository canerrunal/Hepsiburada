"""Shared browser-mode configuration for Hepsiburada Playwright jobs."""

import os

PRODUCT_FIELDS = (
    "marketplace", "product_id", "product_key", "sku", "variant_id", "offer_id", "offer_key", "inventory_key",
    "merchant_id", "merchant_name", "title", "brand", "category_id", "category_name",
    "category_path", "category_product_key", "root_category_id", "root_category_name", "url",
    "canonical_url", "image", "rank", "rank_scope", "source_segment", "source_query",
    "source_page", "segment_position", "price", "original_price", "discount_percent", "currency",
    "stock_status", "stock_quantity", "seller_count", "rating", "rating_count", "review_count",
    "question_count", "campaign", "delivery_summary", "shipping_cost", "captured_at",
    "observed_date", "detail_status", "detail_attempted", "detail_ok", "detail_error",
    "data_sources", "field_availability",
)


def add_browser_mode_args(parser):
    """Add mutually exclusive browser mode flags, defaulting to headless."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Tarayıcıyı arka planda çalıştır (varsayılan)",
    )
    group.add_argument(
        "--headed",
        dest="headless",
        action="store_false",
        help="Debug için Chrome penceresini görünür aç",
    )

    env_value = os.getenv("HB_HEADLESS", "1").strip().lower()
    parser.set_defaults(headless=env_value not in {"0", "false", "no", "off"})
    return parser


def browser_launch_args(headless):
    """Return conservative Chromium flags for the selected browser mode.

    Headful mode is used for the marketplace jobs because the public site
    currently returns HTTP 403 to headless Chromium. The real-browser window
    is placed off-screen so the listing page never takes over the desktop.
    """
    args = ["--disable-blink-features=AutomationControlled"]
    if not headless:
        args.extend(["--window-position=-32000,-32000", "--window-size=1,1"])
    return args
