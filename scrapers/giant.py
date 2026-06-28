"""Giant online scraper.

Giant.sg uses Algolia instantsearch.js for product search.
We intercept the Algolia network requests to capture product data.
If Algolia fails, we fall back to extracting any server-rendered product data.
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


def fetch_products(category_name: str) -> list:
    """Fetch products from Giant by intercepting Algolia responses."""
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

            # Capture Algolia API responses
            algolia_hits = []

            def handle_response(response):
                try:
                    url_lower = response.url.lower()
                    if ("algolia" in url_lower or "algolianet" in url_lower) and response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = response.json()
                            results = data.get("results", [])
                            for result in results:
                                hits = result.get("hits", [])
                                algolia_hits.extend(hits)
                except Exception:
                    pass

            page.on("response", handle_response)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for Algolia to respond (it may take time for the JS to initialize)
            page.wait_for_timeout(15000)

            print(f"[Giant] {category_name}: intercepted {len(algolia_hits)} Algolia hits")

            # Process Algolia hits
            for hit in algolia_hits:
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
                        "category": category_name,
                        "image_url": img_url or "",
                    })

            # If no Algolia hits, try extracting from rendered DOM
            if not products:
                # Try broader selectors for any product-like elements
                all_elements = page.query_selector_all('[class*="product"], [class*="item"], [class*="hit"]')
                print(f"[Giant] {category_name}: fallback - {len(all_elements)} elements with product/item/hit classes")

                for el in all_elements:
                    try:
                        text = el.inner_text().strip()
                        # Look for price patterns in the text
                        price_match = re.search(r'\$[\d.]+', text)
                        if price_match:
                            price = float(price_match.group().replace('$', ''))
                            # Try to extract product name (text before the price)
                            name_part = text[:text.find('$')].strip()
                            if name_part and len(name_part) > 3 and price > 0:
                                img_el = el.query_selector('img')
                                img_url = ""
                                if img_el:
                                    img_url = img_el.get_attribute("src") or ""

                                products.append({
                                    "name": name_part[:100],
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
