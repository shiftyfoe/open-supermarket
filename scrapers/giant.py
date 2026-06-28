"""Giant online scraper using Playwright to intercept Algolia API responses.

Giant.sg uses Algolia instantsearch.js for product search.
We intercept the Algolia API responses to get structured product data.
"""
import json
import re
from datetime import datetime

GIANT_BASE = "https://giant.sg"

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
    """Fetch products from Giant by intercepting Algolia API responses."""
    from playwright.sync_api import sync_playwright

    products = []
    url = f"{GIANT_BASE}/search?q={query}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()

            # Capture Algolia API responses
            algolia_hits = []

            def handle_response(response):
                try:
                    if "algolia" in response.url and response.status == 200:
                        data = response.json()
                        results = data.get("results", [])
                        for result in results:
                            hits = result.get("hits", [])
                            algolia_hits.extend(hits)
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for Algolia to respond
            page.wait_for_timeout(8000)

            print(f"[Giant] {query}: intercepted {len(algolia_hits)} Algolia hits")

            for hit in algolia_hits:
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

            browser.close()
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
    for cat in CATEGORIES:
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
