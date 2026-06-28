"""Cold Storage online scraper.

Cold Storage (coldstorage.com.sg) is a Next.js App Router site with
server-rendered product cards. We parse the HTML using BeautifulSoup.

CSS class names follow the pattern: product-item_product-item__{name}__{hash}
We use partial attribute selectors ([class*="..."]) for resilience against
frontend redeployments that change the hash suffixes.
"""
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

COLDSTORAGE_SEARCH = "https://coldstorage.com.sg/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-SG,en;q=0.9",
}

# Search queries — each returns up to 30 products
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

# Delay between requests to be polite
REQUEST_DELAY = 1.0  # seconds
MAX_RETRIES = 3


def fetch_products(query: str) -> list:
    """Fetch products from Cold Storage search.

    Uses partial CSS class selectors to survive frontend redeployments
    that change CSS-module hash suffixes.
    """
    params = {"q": query}
    products = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                COLDSTORAGE_SEARCH,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Use partial selectors — match the stable prefix, ignore hash suffix
            for item in soup.select('[class*="product-item_product-item__BWbnO"]'):
                name_elem = item.select_one('[class*="product-item_product-item__name__"]')
                price_elem = item.select_one('[class*="product-price_product-price__price__"]')
                img_elem = item.select_one('[class*="product-item_product-item__img__"]')
                link_elem = item.select_one('[class*="product-item_product-item__img-link__"]')

                if not name_elem or not price_elem:
                    continue

                name = name_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)

                # Extract price from "$3.20" or "S$3.20" format
                price_match = re.search(r'[\$S]*([\d.]+)', price_text)
                if not price_match:
                    continue

                price = float(price_match.group(1))
                if price <= 0:
                    continue

                # Extract product URL (relative path)
                product_url = ""
                if link_elem:
                    href = link_elem.get("href", "")
                    if href and not href.startswith("http"):
                        product_url = f"https://coldstorage.com.sg{href}"
                    else:
                        product_url = href

                # Extract image URL
                image_url = ""
                if img_elem:
                    image_url = img_elem.get("src", "")

                products.append({
                    "name": name,
                    "price": price,
                    "category": query,
                    "image_url": image_url,
                    "product_url": product_url,
                })

            print(f"[ColdStorage] {query}: {len(products)} products")
            return products

        except requests.RequestException as e:
            print(f"[ColdStorage] {query}: attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)  # exponential backoff

    return products


def parse_product(raw: dict) -> dict:
    """Extract relevant fields from raw product data.

    Attempts to extract brand and size from the product name using heuristics.
    """
    name = raw.get("name", "")

    # Try to extract brand (first word or two, before common size patterns)
    brand = _extract_brand(name)

    # Try to extract size/weight from name (e.g. "5kg", "300g", "1L")
    size = _extract_size(name)

    product_id = re.sub(r'[^a-z0-9]', '_', name.lower())[:30]
    return {
        "id": f"cs_{product_id}",
        "supermarket": "coldstorage",
        "name": name,
        "brand": brand,
        "category": raw.get("category", ""),
        "price": raw.get("price", 0),
        "original_price": raw.get("price", 0),
        "unit": size,
        "size": size,
        "image_url": raw.get("image_url", ""),
        "product_url": raw.get("product_url", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def _extract_brand(name: str) -> str:
    """Heuristic to extract brand from product name.

    Common patterns:
    - "Songhe Thai Fragrant White Rice 5kg" → "Songhe"
    - "Naturel Organic Brown Rice Fusilli 250g" → "Naturel"
    - "FairPrice Fresh Whole Chicken" → "FairPrice"
    """
    # Skip generic product names
    if not name:
        return ""

    # Take first word as brand (most SG grocery brands are single words)
    first_word = name.split()[0]
    # Skip if it looks like a descriptor, not a brand
    skip_words = {"fresh", "frozen", "organic", "premium", "imported", "local", "the"}
    if first_word.lower() in skip_words:
        return ""

    return first_word


def _extract_size(name: str) -> str:
    """Extract size/weight from product name.

    Matches patterns like: 5kg, 300g, 1L, 500ml, 1.5kg, 2 x 500g
    """
    # Match size patterns at the end of the name
    match = re.search(r'(\d+(?:\.\d+)?\s*(?:x\s*)?\d*(?:kg|g|l|ml|L|pcs|pack|pkt|sachets?))\s*$', name, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Also match standalone numbers with units anywhere in name
    match = re.search(r'(\d+(?:\.\d+)?\s*(?:kg|g|ml|L))\b', name, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return ""


def scrape() -> list:
    """Scrape all tracked categories from Cold Storage."""
    all_products = []
    seen_ids = set()

    for i, cat in enumerate(CATEGORIES):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        raw = fetch_products(cat)
        for p in raw:
            parsed = parse_product(p)
            if parsed["price"] > 0 and parsed["id"] not in seen_ids:
                seen_ids.add(parsed["id"])
                all_products.append(parsed)

    return all_products


if __name__ == "__main__":
    products = scrape()
    print(f"[ColdStorage] Scraped {len(products)} products")
    with open("data/coldstorage.json", "w") as f:
        json.dump(products, f, indent=2)
