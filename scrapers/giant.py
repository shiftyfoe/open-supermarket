"""Giant online scraper using Algolia search API.

Giant.sg uses Algolia instantsearch.js. We try multiple Algolia endpoint
formats since the DSN URL may not resolve from all networks.
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

# Try multiple Algolia endpoint formats
ALGOLIA_URLS = [
    f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries",
    f"https://{ALGOLIA_APP_ID}.algolia.net/1/indexes/*/queries",
    "https://algolia.net/1/indexes/*/queries",
]

HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

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


def fetch_products(query: str) -> list:
    """Fetch products from Giant via Algolia API, trying multiple endpoints."""
    products = []

    payload = {
        "requests": [{
            "indexName": ALGOLIA_INDEX,
            "params": f"query={query}&hitsPerPage=40",
        }]
    }

    for url in ALGOLIA_URLS:
        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                hits = results[0].get("hits", [])
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
                print(f"[Giant] {query}: {len(products)} products from {url}")
                return products
        except Exception:
            continue

    print(f"[Giant] {query}: all Algolia endpoints failed")
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
