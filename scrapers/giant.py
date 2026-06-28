"""Giant online scraper."""
import json
import requests
from datetime import datetime

GIANT_API = "https://api.giant.com.sg/v1"

CATEGORIES = [
    "rice",
    "cooking-oil",
    "milk",
    "eggs",
    "bread",
    "chicken",
    "pork",
    "fish",
    "vegetables",
    "fruits",
    "canned-food",
    "instant-noodles",
]


def fetch_products(category: str, limit: int = 20) -> list:
    """Fetch products from Giant API."""
    url = f"{GIANT_API}/products"
    params = {
        "category": category,
        "limit": limit,
        "sort": "bestselling",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"[Giant] Error fetching {category}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    return {
        "id": f"gi_{raw.get('sku', '')}",
        "supermarket": "giant",
        "name": raw.get("title", ""),
        "brand": raw.get("brand", ""),
        "category": raw.get("category", ""),
        "price": float(raw.get("sellingPrice", 0)),
        "original_price": float(raw.get("regularPrice", 0)),
        "unit": raw.get("uom", ""),
        "size": raw.get("size", ""),
        "image_url": raw.get("imageUrl", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Giant."""
    all_products = []
    for cat in CATEGORIES:
        raw = fetch_products(cat)
        for p in raw:
            parsed = parse_product(p)
            if parsed["price"] > 0:
                all_products.append(parsed)
    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[Giant] Scraped {len(products)} products")
    with open("data/giant.json", "w") as f:
        json.dump(products, f, indent=2)
