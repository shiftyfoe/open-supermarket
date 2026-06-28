"""Cold Storage online scraper."""
import json
import requests
from datetime import datetime

COLDSTORAGE_API = "https://api.coldstorage.com.sg/v1"

CATEGORIES = [
    "rice-grains",
    "cooking-oil",
    "milk-dairy",
    "eggs",
    "bread",
    "meat",
    "seafood",
    "vegetables",
    "fruits",
    "canned-food",
]


def fetch_products(category: str, limit: int = 20) -> list:
    """Fetch products from Cold Storage API."""
    url = f"{COLDSTORAGE_API}/products"
    params = {
        "category": category,
        "limit": limit,
        "sort": "popular",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("products", [])
    except Exception as e:
        print(f"[ColdStorage] Error fetching {category}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    return {
        "id": f"cs_{raw.get('productId', '')}",
        "supermarket": "coldstorage",
        "name": raw.get("productName", ""),
        "brand": raw.get("brandName", ""),
        "category": raw.get("categoryName", ""),
        "price": float(raw.get("price", 0)),
        "original_price": float(raw.get("listPrice", 0)),
        "unit": raw.get("uom", ""),
        "size": raw.get("packageSize", ""),
        "image_url": raw.get("imageUrl", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Cold Storage."""
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
    print(f"[ColdStorage] Scraped {len(products)} products")
    with open("data/coldstorage.json", "w") as f:
        json.dump(products, f, indent=2)
