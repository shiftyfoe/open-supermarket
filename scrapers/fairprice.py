"""FairPrice online scraper."""
import json
import requests
from datetime import datetime

FAIRPRICE_API = "https://website-api.omni.fairprice.com.sg/product/v2"

# Common SKU categories to track
CATEGORIES = [
    "rice",
    "cooking-oil",
    "milk",
    "eggs",
    "bread",
    "chicken",
    "pork",
    "vegetables",
    "instant-noodles",
    "canned-food",
]


def fetch_products(category: str, limit: int = 20) -> list:
    """Fetch products from FairPrice API for a given category."""
    params = {
        "category": category,
        "limit": limit,
        "sort": "popularity",
    }
    try:
        resp = requests.get(FAIRPRICE_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("products", [])
    except Exception as e:
        print(f"[FairPrice] Error fetching {category}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    return {
        "id": f"fp_{raw.get('id', '')}",
        "supermarket": "fairprice",
        "name": raw.get("name", ""),
        "brand": raw.get("brand", ""),
        "category": raw.get("category", ""),
        "price": raw.get("price", {}).get("current", 0),
        "original_price": raw.get("price", {}).get("original", 0),
        "unit": raw.get("unitOfMeasure", ""),
        "size": raw.get("size", ""),
        "image_url": raw.get("image", {}).get("url", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from FairPrice."""
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
    print(f"[FairPrice] Scraped {len(products)} products")
    with open("data/fairprice.json", "w") as f:
        json.dump(products, f, indent=2)
