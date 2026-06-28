"""Sheng Siong online scraper using web scraping."""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

SHENGSIONG_SEARCH = "https://www.shengsiong.com.sg/search"

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
    """Fetch products from Sheng Siong search."""
    url = f"{SHENGSIONG_SEARCH}/{query}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        products = []
        # Sheng Siong uses various product card selectors
        for item in soup.select('.product-card, .product-item, .product-tile, [class*=product]'):
            name_elem = item.select_one('[class*=name], [class*=title], h3, h4')
            price_elem = item.select_one('[class*=price]')

            if name_elem and price_elem:
                name = name_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                # Extract price from "$3.20" or "S$3.20" format
                price_match = re.search(r'[\$S]*([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    if price > 0:
                        products.append({
                            "name": name,
                            "price": price,
                            "category": query,
                        })
        return products
    except Exception as e:
        print(f"[ShengSiong] Error fetching {query}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data."""
    product_id = re.sub(r'[^a-z0-9]', '_', raw.get('name', '').lower())[:30]
    return {
        "id": f"ss_{product_id}",
        "supermarket": "shengsiong",
        "name": raw.get("name", ""),
        "brand": "",
        "category": raw.get("category", ""),
        "price": raw.get("price", 0),
        "original_price": raw.get("price", 0),
        "unit": "",
        "size": "",
        "image_url": "",
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
