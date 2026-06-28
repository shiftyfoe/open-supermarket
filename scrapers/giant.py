"""Giant online scraper using web scraping.

Giant.sg is a server-rendered e-commerce site (Yii framework).
Products are in the HTML — no JS rendering needed.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

GIANT_BASE = "https://giant.sg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

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
    """Fetch products from Giant search page."""
    url = f"{GIANT_BASE}/search"
    params = {"q": query}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        products = []
        # Giant uses product card elements — try common selectors
        items = soup.select('.product-item, .product-card, .product-tile, [class*="product-card"]')

        if not items:
            # Fallback: look for structured product data in the page
            items = soup.select('[class*="product"]')

        print(f"[Giant] {query}: found {len(items)} candidate elements")

        for item in items:
            name_el = item.select_one('[class*="name"], [class*="title"], h3, h4, .product-name')
            price_el = item.select_one('[class*="price"], .product-price')
            img_el = item.select_one('img')
            link_el = item.select_one('a[href*="/product/"], a[href*="/p/"]')

            if name_el and price_el:
                name = name_el.get_text(strip=True)
                price_text = price_el.get_text(strip=True)

                price_match = re.search(r'[\$S]*([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    if price > 0 and len(name) > 2:
                        img_url = ""
                        if img_el:
                            img_url = img_el.get("src") or img_el.get("data-src") or ""

                        product_url = ""
                        if link_el:
                            product_url = link_el.get("href", "")

                        products.append({
                            "name": name,
                            "price": price,
                            "category": query,
                            "image_url": img_url,
                            "product_url": product_url,
                        })
        return products
    except Exception as e:
        print(f"[Giant] Error fetching {query}: {e}")
        return []


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
