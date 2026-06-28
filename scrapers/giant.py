"""Giant online scraper using Algolia API."""
import json
import re
import requests
from datetime import datetime

import os

GIANT_ALGOLIA_APP_ID = os.environ.get("GIANT_ALGOLIA_APP_ID", "")
GIANT_ALGOLIA_API_KEY = os.environ.get("GIANT_ALGOLIA_API_KEY", "")
GIANT_ALGOLIA_URL = f"https://{GIANT_ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"

HEADERS = {
    "X-Algolia-Application-Id": GIANT_ALGOLIA_APP_ID,
    "X-Algolia-API-Key": GIANT_ALGOLIA_API_KEY,
    "Content-Type": "application/json",
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


def fetch_products(query: str, limit: int = 20) -> list:
    """Fetch products from Giant via Algolia API."""
    payload = {
        "requests": [{
            "indexName": "giant_products",
            "params": f"query={query}&hitsPerPage={limit}",
        }]
    }
    try:
        resp = requests.post(GIANT_ALGOLIA_URL, headers=HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            return results[0].get("hits", [])
        return []
    except Exception as e:
        print(f"[Giant] Error fetching {query}: {e}")
        return []


def parse_product(raw: dict, category: str) -> dict:
    """Extract relevant fields from raw Algolia hit."""
    # Extract price from various possible fields
    price = 0
    for field in ["price", "sellingPrice", "currentPrice"]:
        if field in raw and raw[field]:
            try:
                price = float(raw[field])
                break
            except (ValueError, TypeError):
                pass

    return {
        "id": f"gi_{raw.get('objectID', '')}",
        "supermarket": "giant",
        "name": raw.get("name", raw.get("title", "")),
        "brand": raw.get("brand", ""),
        "category": category,
        "price": price,
        "original_price": float(raw.get("originalPrice", raw.get("regularPrice", price))),
        "unit": raw.get("uom", raw.get("unit", "")),
        "size": raw.get("size", raw.get("packageSize", "")),
        "image_url": raw.get("imageUrl", raw.get("image", "")),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Giant."""
    all_products = []
    for cat in CATEGORIES:
        raw = fetch_products(cat)
        for p in raw:
            parsed = parse_product(p, cat)
            if parsed["price"] > 0:
                all_products.append(parsed)
    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[Giant] Scraped {len(products)} products")
    with open("data/giant.json", "w") as f:
        json.dump(products, f, indent=2)
