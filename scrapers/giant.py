"""Giant online scraper using Algolia search API."""
import json
import re
import requests
from datetime import datetime

# Giant.sg embeds these in their page source (search-only key, safe to hardcode)
GIANT_ALGOLIA_APP_ID = "PFCHI1YM66"
GIANT_ALGOLIA_API_KEY = "d0c09a40111717aec861992cf8497e71"
GIANT_ALGOLIA_INDEX = "giant_product_live"
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


def fetch_products(query: str, limit: int = 40) -> list:
    """Fetch products from Giant via Algolia API."""
    payload = {
        "requests": [{
            "indexName": GIANT_ALGOLIA_INDEX,
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
    # Giant's Algolia records have nested price info
    price = 0
    for field in ["price", "sellingPrice", "currentPrice", "finalPrice"]:
        if field in raw and raw[field]:
            try:
                price = float(raw[field])
                break
            except (ValueError, TypeError):
                pass

    # Check for nested price object
    if price == 0 and isinstance(raw.get("price"), dict):
        try:
            price = float(raw["price"].get("amount", 0))
        except (ValueError, TypeError):
            pass

    original_price = price
    for field in ["originalPrice", "regularPrice", "listPrice"]:
        if field in raw and raw[field]:
            try:
                original_price = float(raw[field])
                break
            except (ValueError, TypeError):
                pass

    name = raw.get("name", raw.get("title", ""))
    return {
        "id": f"gi_{raw.get('objectID', '')}",
        "supermarket": "giant",
        "name": name,
        "brand": raw.get("brand", ""),
        "category": category,
        "price": price,
        "original_price": original_price,
        "unit": raw.get("uom", raw.get("unit", "")),
        "size": raw.get("size", raw.get("packageSize", "")),
        "image_url": raw.get("imageUrl", raw.get("image", raw.get("thumbnail", ""))),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Giant."""
    all_products = []
    seen_ids = set()
    for cat in CATEGORIES:
        raw = fetch_products(cat)
        for p in raw:
            parsed = parse_product(p, cat)
            if parsed["price"] > 0 and parsed["id"] not in seen_ids:
                seen_ids.add(parsed["id"])
                all_products.append(parsed)
    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[Giant] Scraped {len(products)} products")
    with open("data/giant.json", "w") as f:
        json.dump(products, f, indent=2)
