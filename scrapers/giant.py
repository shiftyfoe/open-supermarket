"""Giant online scraper.

Giant.sg uses Algolia for search but the Algolia DNS endpoint is unreachable from CI.
We try Algolia API first (requests), then fall back to scraping category pages (Playwright).
"""
import json
import re
import requests
from datetime import datetime

GIANT_BASE = "https://giant.sg"

# Giant Algolia config (from page source — search-only key)
ALGOLIA_APP_ID = "PFCHI1YM66"
ALGOLIA_API_KEY = "d0c09a40111717aec861992cf8497e71"
ALGOLIA_INDEX = "giant_product_live"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"

# Category page slugs on giant.sg
CATEGORY_PAGES = {
    "rice": "rice",
    "oil": "cooking-oil",
    "milk": "fresh-milk",
    "eggs": "eggs",
    "chicken": "chicken",
    "bread": "bread",
    "noodles": "instant-noodles",
    "tuna": "canned-tuna",
}

HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}


def fetch_via_algolia(query: str) -> list:
    """Try fetching products via Algolia API."""
    payload = {
        "requests": [{
            "indexName": ALGOLIA_INDEX,
            "params": f"query={query}&hitsPerPage=40",
        }]
    }
    try:
        resp = requests.post(ALGOLIA_URL, headers=HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            return results[0].get("hits", [])
    except Exception:
        pass
    return []


def fetch_via_category_page(category_name: str) -> list:
    """Scrape products from a Giant category page using Playwright."""
    from playwright.sync_api import sync_playwright

    slug = CATEGORY_PAGES.get(category_name, category_name)
    url = f"{GIANT_BASE}/{slug}"
    products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            content_len = len(page.content())
            print(f"[Giant] {category_name}: page content length = {content_len}")

            # Look for product items
            items = page.query_selector_all('.product-item, .product-card, [class*="product-item"], [class*="product-card"]')
            print(f"[Giant] {category_name}: found {len(items)} product items")

            for item in items:
                try:
                    name_el = item.query_selector('[class*="name"], [class*="title"], h3, h4')
                    price_el = item.query_selector('[class*="price"]')
                    img_el = item.query_selector('img')

                    if name_el and price_el:
                        name = name_el.inner_text().strip()
                        price_text = price_el.inner_text().strip()

                        price_match = re.search(r'[\$S]*([\d.]+)', price_text)
                        if price_match:
                            price = float(price_match.group(1))
                            if price > 0 and len(name) > 2:
                                img_url = ""
                                if img_el:
                                    img_url = img_el.get_attribute("src") or ""

                                products.append({
                                    "name": name,
                                    "price": price,
                                    "category": category_name,
                                    "image_url": img_url,
                                })
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        print(f"[Giant] Error fetching {category_name}: {e}")

    return products


def fetch_products(query: str) -> list:
    """Fetch products — try Algolia API first, fall back to category page scraping."""
    # Try Algolia API (fast, structured data)
    hits = fetch_via_algolia(query)
    if hits:
        products = []
        for hit in hits:
            name = hit.get("name", hit.get("title", ""))
            price = 0
            for field in ["price", "sellingPrice", "currentPrice", "finalPrice"]:
                if field in hit and hit[field]:
                    try:
                        price = float(hit[field])
                        break
                    except (ValueError, TypeError):
                        pass

            if isinstance(price, dict):
                try:
                    price = float(price.get("amount", 0))
                except (ValueError, TypeError):
                    price = 0

            if price > 0 and name:
                img_url = hit.get("imageUrl", hit.get("image", hit.get("thumbnail", "")))
                products.append({
                    "name": name,
                    "price": price,
                    "category": query,
                    "image_url": img_url or "",
                })
        print(f"[Giant] {query}: {len(products)} products via Algolia")
        return products

    # Fall back to category page scraping
    return fetch_via_category_page(query)


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    product_id = re.sub(r'[^a-z0-9]', '_', raw.get('name', '').lower())[:30]
    return {
        "id": f"gi_{product_id}",
        "supermarket": "giant",
        "name": raw.get("name", ""),
        "brand": "",
        "category": raw.get("category", ""),
        "price": raw.get("price", 0),
        "original_price": raw.get("price", 0),
        "unit": "",
        "size": "",
        "image_url": raw.get("image_url", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Giant."""
    all_products = []
    seen_ids = set()
    for cat in CATEGORY_PAGES:
        raw = fetch_products(cat)
        for p in raw:
            parsed = parse_product(p)
            if parsed["price"] > 0 and parsed["id"] not in seen_ids:
                seen_ids.add(parsed["id"])
                all_products.append(parsed)
    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[Giant] Scraped {len(products)} products")
    with open("data/giant.json", "w") as f:
        json.dump(products, f, indent=2)
