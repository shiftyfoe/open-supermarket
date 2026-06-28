"""Sheng Siong online scraper using Playwright with stealth plugin.

Sheng Siong is a Meteor.js SPA behind Incapsula CDN.
We use playwright-stealth to bypass Incapsula's bot detection,
then call Meteor DDP methods from the rendered page context.
"""
import json
import re
from datetime import datetime

SHENGSIONG_BASE = "https://www.shengsiong.com.sg"

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
    """Fetch products from Sheng Siong by calling Meteor methods from page context."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-SG",
                java_script_enabled=True,
            )
            page = context.new_page()
            stealth_sync(page)

            # Navigate to homepage first to get Incapsula cookies
            page.goto(SHENGSIONG_BASE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            content_len = len(page.content())
            print(f"[ShengSiong] {query}: homepage content length = {content_len}")

            if content_len < 2000:
                # Still blocked by Incapsula
                print(f"[ShengSiong] {query}: blocked by Incapsula ({content_len} bytes)")
                browser.close()
                return products

            # Now call Meteor DDP method from the page context
            try:
                result = page.evaluate(f"""
                    async () => {{
                        return new Promise((resolve, reject) => {{
                            const filters = {{
                                categoryFilter: {{slugs: []}},
                                campaignPageFilter: {{slug: "", category: {{slug: ""}}}},
                                shoppingListFilter: {{slug: "", category: {{slug: ""}}, search: {{slug: ""}}, showKeptForLater: false}},
                                searchFilter: {{slug: "{query}", category: {{slug: ""}}}},
                                preOrderCampaignFilter: {{slug: "", category: {{slug: ""}}}},
                                ecommPromotionFilter: {{active: true, category: {{slug: ""}}}},
                            }};
                            const misc = {{
                                brands: {{slugs: []}},
                                prices: {{slugs: []}},
                                countryOfOrigins: {{slugs: []}},
                                dietaryHabits: {{slugs: []}},
                                tags: {{slugs: []}},
                                promotionTypes: {{slugs: []}},
                                sortBy: {{slug: ""}},
                            }};

                            if (typeof Meteor === 'undefined') {{
                                reject(new Error("Meteor not available"));
                                return;
                            }}

                            Meteor.call("Products.getByAllSlugs", filters, misc, 1, 40, (err, res) => {{
                                if (err) reject(err);
                                else resolve(res);
                            }});
                        }});
                    }}
                """)

                if result and isinstance(result, list):
                    for item in result:
                        name = item.get("name", "")
                        price = item.get("price", item.get("finalPrice", 0))
                        if isinstance(price, dict):
                            price = price.get("amount", 0)
                        try:
                            price = float(price)
                        except (ValueError, TypeError):
                            price = 0

                        if price > 0 and name:
                            img = ""
                            images = item.get("images", [])
                            if images and isinstance(images, list):
                                img = images[0] if isinstance(images[0], str) else images[0].get("url", "")

                            products.append({
                                "name": name,
                                "price": price,
                                "category": query,
                                "image_url": img,
                            })
                    print(f"[ShengSiong] {query}: got {len(products)} products via Meteor.call")
            except Exception as e:
                print(f"[ShengSiong] {query}: Meteor.call error: {e}")

            browser.close()
    except Exception as e:
        print(f"[ShengSiong] Error fetching {query}: {e}")

    return products


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
        "image_url": raw.get("image_url", ""),
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories from Sheng Siong."""
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
    print(f"[ShengSiong] Scraped {len(products)} products")
    with open("data/shengsiong.json", "w") as f:
        json.dump(products, f, indent=2)
