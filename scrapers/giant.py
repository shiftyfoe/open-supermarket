"""Giant online scraper using Algolia search API.

Giant.sg uses Algolia for product search.
We use the official algoliasearch client which handles endpoint resolution
and retries automatically.
"""
import json
import re
from datetime import datetime

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


def fetch_products(query: str) -> list:
    """Fetch products from Giant via Algolia search client."""
    from algoliasearch.search_client import SearchClient

    products = []

    try:
        client = SearchClient.create(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
        index = client.init_index(ALGOLIA_INDEX)

        result = index.search(query, {
            "hitsPerPage": 40,
        })

        hits = result.get("hits", [])
        print(f"[Giant] {query}: got {len(hits)} Algolia hits")

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
