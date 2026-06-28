"""Giant online scraper using Playwright for Algolia search rendering.

Giant.sg uses Algolia instantsearch.js for search — server returns 404 for /search.
Playwright renders the client-side search and extracts product data.
"""
import json
import re
from datetime import datetime

GIANT_BASE = "https://giant.sg"

# Common categories to track
CATEGORIES = [
    "rice",
    "oil",
    "milk",
    "eggs",
    "chicken",
    "bread",
    "noodles",
    "tuna",
]


def fetch_products(query: str) -> list:
    """Fetch products from Giant by rendering the Algolia search with Playwright."""
    from playwright.sync_api import sync_playwright

    products = []
    url = f"{GIANT_BASE}/search?q={query}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for Algolia results to render
            page.wait_for_timeout(8000)

            content = page.content()
            content_len = len(content)
            print(f"[Giant] {query}: page content length = {content_len}")

            # Giant uses product card elements
            items = page.query_selector_all('.product-item, .product-card, .product-tile, [class*="product-card"], [class*="product-item"]')
            print(f"[Giant] {query}: found {len(items)} items with product selectors")

            if not items:
                items = page.query_selector_all('[class*="product"]')
                print(f"[Giant] {query}: fallback found {len(items)} items")

            for item in items:
                try:
                    name_el = item.query_selector('[class*="name"], [class*="title"], h3, h4, .product-name')
                    price_el = item.query_selector('[class*="price"], .product-price')
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
                                    img_url = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""

                                products.append({
                                    "name": name,
                                    "price": price,
                                    "category": query,
                                    "image_url": img_url,
                                })
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        print(f"[Giant] Error fetching {query}: {e}")

    return products


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
    for cat in CATEGORIES:
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
