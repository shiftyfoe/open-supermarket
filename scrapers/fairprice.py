"""FairPrice online scraper using their API."""
import json
import requests
from datetime import datetime

FAIRPRICE_API = "https://website-api.omni.fairprice.com.sg/api/product/v2"
FAIRPRICE_CATEGORY_API = "https://website-api.omni.fairprice.com.sg/api/category"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.fairprice.com.sg",
    "Referer": "https://www.fairprice.com.sg/",
}

# Category slugs for common products
CATEGORIES = {
    "rice": "rice-14",
    "oil": "oil",
    "fresh-milk": "fresh-milk--1",
    "eggs": "eggs",
    "chicken": "chicken",
    "noodles": "noodles--1",
    "canned-food": "canned-food",
    "bread": "bread--bakery",
}


def fetch_categories() -> dict:
    """Fetch all categories from FairPrice API."""
    try:
        resp = requests.get(FAIRPRICE_CATEGORY_API, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        categories = data.get("data", {}).get("category", [])
        result = {}
        for cat in categories:
            result[cat["slug"]] = cat["name"]
            for sub in cat.get("subCategories", []):
                result[sub["slug"]] = sub["name"]
        return result
    except Exception as e:
        print(f"[FairPrice] Error fetching categories: {e}")
        return {}


def fetch_products(category_slug: str, page: int = 1) -> list:
    """Fetch products from FairPrice API for a given category."""
    params = {
        "category": category_slug,
        "collectionSlug": category_slug,
        "collectionType": "category",
        "includeTagDetails": "true",
        "page": page,
        "pageType": "category",
        "slug": category_slug,
        "url": category_slug,
    }
    try:
        resp = requests.get(FAIRPRICE_API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("product", [])
    except Exception as e:
        print(f"[FairPrice] Error fetching {category_slug}: {e}")
        return []


def parse_product(raw: dict, category: str) -> dict:
    """Extract relevant fields from raw product data."""
    brand_data = raw.get("brand", {})
    return {
        "id": f"fp_{raw.get('clientItemId', '')}",
        "supermarket": "fairprice",
        "name": raw.get("name", ""),
        "brand": brand_data.get("name", "") if brand_data else "",
        "category": category,
        "price": float(raw.get("final_price", 0)),
        "original_price": float(raw.get("final_price", 0)),
        "unit": raw.get("metaData", {}).get("DisplayUnit", ""),
        "size": raw.get("metaData", {}).get("DisplayUnit", ""),
        "image_url": raw.get("images", [""])[0] if raw.get("images") else "",
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from FairPrice."""
    all_products = []
    for name, slug in CATEGORIES.items():
        raw = fetch_products(slug)
        for p in raw:
            parsed = parse_product(p, name)
            if parsed["price"] > 0:
                all_products.append(parsed)
    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[FairPrice] Scraped {len(products)} products")
    with open("data/fairprice.json", "w") as f:
        json.dump(products, f, indent=2)
