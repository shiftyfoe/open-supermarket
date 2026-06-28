"""Sheng Siong online scraper using Playwright for JS rendering.

Sheng Siong is a Meteor.js SPA — plain HTTP requests get an empty shell.
Playwright renders the full page so we can extract product data.
"""
import json
import re
from datetime import datetime

SHENGSIONG_BASE = "https://www.shengsiong.com.sg"

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
    """Fetch products from Sheng Siong by rendering the search page with Playwright."""
    from playwright.sync_api import sync_playwright

    products = []
    url = f"{SHENGSIONG_BASE}/search/{query}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for product cards to appear
            try:
                page.wait_for_selector('[class*="product"]', timeout=10000)
            except Exception:
                # If no product elements found, return empty
                browser.close()
                return products

            # Extract product data from the rendered page
            # Sheng Siong uses CSS modules with hashed class names,
            # so we look for common patterns
            items = page.query_selector_all('[class*="product-card"], [class*="product-item"], [class*="ProductCard"]')

            if not items:
                # Fallback: try broader selectors
                items = page.query_selector_all('[class*="product"]')

            for item in items:
                try:
                    # Find name element
                    name_el = item.query_selector('[class*="name"], [class*="title"], h3, h4')
                    # Find price element
                    price_el = item.query_selector('[class*="price"]')
                    # Find image
                    img_el = item.query_selector('img')

                    if name_el and price_el:
                        name = name_el.inner_text().strip()
                        price_text = price_el.inner_text().strip()

                        # Extract price from "$3.20" or "S$3.20" format
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
                                    "category": query,
                                    "image_url": img_url,
                                })
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        print(f"[ShengSiong] Error fetching {query}: {e}")

    return products


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    product_id = re.sub(r'[^a-z0-9]', '_', raw.get('name', '').lower())[:30]
    return {
        "id": f"ss_{product_id}",
        "supermarket": "shengsiong",
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
    """Scrape all tracked categories from Sheng Siong."""
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
    print(f"[ShengSiong] Scraped {len(products)} products")
    with open("data/shengsiong.json", "w") as f:
        json.dump(products, f, indent=2)
