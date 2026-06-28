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
            all_requests = []

            def handle_response(response):
                try:
                    all_requests.append(response.url[:100])
                    # Check for Algolia API calls or any failed requests
                    if "algolia" in response.url.lower() and "js" not in response.url:
                        print(f"[Giant] {query}: Algolia response: {response.status} {response.url[:100]}")
                        if response.status == 200:
                            data = response.json()
                            results = data.get("results", [])
                            for result in results:
                                hits = result.get("hits", [])
                                algolia_hits.extend(hits)
                    elif response.status >= 400 and "giant.sg" in response.url:
                        print(f"[Giant] {query}: Failed request: {response.status} {response.url[:100]}")
                except Exception as e:
                    print(f"[Giant] {query}: response error: {e}")

            page.on("response", handle_response)

            # Giant's /search URL returns 404 — search is entirely client-side.
            # Navigate to homepage, then use the search box to trigger Algolia.
            page.goto(GIANT_BASE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Find and use the search input
            search_input = page.query_selector('input[type="search"], input[name="q"], input[placeholder*="search" i], #search, .search-input')
            if search_input:
                search_input.fill(query)
                search_input.press("Enter")
                page.wait_for_timeout(8000)
            else:
                print(f"[Giant] {query}: no search input found")

            # Wait for Algolia to respond
            page.wait_for_timeout(8000)

            # Try to get Algolia config from the page
            try:
                algolia_config = page.evaluate("typeof site_config !== 'undefined' ? site_config.algolia : null")
                if algolia_config:
                    print(f"[Giant] {query}: Algolia config from page: {algolia_config}")
            except Exception:
                pass

            print(f"[Giant] {query}: intercepted {len(algolia_hits)} Algolia hits, {len(all_requests)} total requests")

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
