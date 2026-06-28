"""Sheng Siong online scraper."""
import json
import requests
from datetime import datetime

SHENGSIONG_BASE = "https://www.shengsiong.com.sg/api"

CATEGORIES = [
    "rice-noodles",
    "cooking-essentials",
    "dairy-eggs",
    "meat-seafood",
    "fruits-vegetables",
    "bread-bakery",
    "canned-food",
    "beverages",
]


def fetch_products(category: str, limit: int = 20) -> list:
    """Fetch products from Sheng Siong for a given category."""
    url = f"{SHENGSIONG_BASE}/products"
    params = {
        "category": category,
        "limit": limit,
        "page": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"[ShengSiong] Error fetching {category}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    return {
        "id": f"ss_{raw.get('sku', '')}",
        "supermarket": "shengsiong",
        "name": raw.get("name", ""),
        "brand": raw.get("brand", ""),
        "category": raw.get("category", ""),
        "price": float(raw.get("price", 0)),
        "original_price": float(raw.get("originalPrice", 0)),
        "unit": raw.get("unit", ""),
        "size": raw.get("weight", ""),
        "image_url": raw.get("imageUrl", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Sheng Siong."""
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
    print(f"[ShengSiong] Scraped {len(products)} products")
    with open("data/shengsiong.json", "w") as f:
        json.dump(products, f, indent=2)
