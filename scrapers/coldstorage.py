"""Cold Storage online scraper using web scraping."""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

COLDSTORAGE_SEARCH = "https://coldstorage.com.sg/search"

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
    """Fetch products from Cold Storage search."""
    params = {"q": query}
    try:
        resp = requests.get(COLDSTORAGE_SEARCH, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        products = []
        for item in soup.select('.product-item_product-item__BWbnO'):
            name_elem = item.select_one('.product-item_product-item__name__piwWX')
            price_elem = item.select_one('.product-price_product-price__price__qk_1n')
            img_elem = item.select_one('.product-item_product-item__img__hxMOm img')
            link_elem = item.select_one('.product-item_product-item__img-link__FJWGM')

            if name_elem and price_elem:
                name = name_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                # Extract price from "$3.20" format
                price_match = re.search(r'[\$S]*([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    products.append({
                        "name": name,
                        "price": price,
                        "category": query,
                        "image_url": img_elem.get('src', '') if img_elem else '',
                        "product_url": link_elem.get('href', '') if link_elem else '',
                    })
        return products
    except Exception as e:
        print(f"[ColdStorage] Error fetching {query}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    # Generate a unique ID from the product name
    product_id = re.sub(r'[^a-z0-9]', '_', raw.get('name', '').lower())[:30]
    return {
        "id": f"cs_{product_id}",
        "supermarket": "coldstorage",
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
