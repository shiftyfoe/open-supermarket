"""Sheng Siong online scraper using Meteor DDP protocol.

Sheng Siong is a Meteor.js SPA behind Incapsula CDN.
We bypass the frontend entirely by calling Meteor server methods via DDP.
"""
import json
import re
import uuid
import websocket
from datetime import datetime

DDP_URL = "wss://www.shengsiong.com.sg/sockjs/websocket"

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


def ddp_connect(ws):
    """Send DDP connect message."""
    ws.send(json.dumps({"msg": "connect", "version": "1", "support": ["1", "pre2", "pre1"]}))
    # Wait for connected response
    while True:
        resp = json.loads(ws.recv())
        if resp.get("msg") == "connected":
            return resp
        if resp.get("msg") == "failed":
            raise Exception(f"DDP connect failed: {resp}")


def ddp_call(ws, method, params, call_id=None):
    """Call a Meteor method via DDP and return the result."""
    if call_id is None:
        call_id = str(uuid.uuid4())[:8]
    ws.send(json.dumps({
        "msg": "method",
        "method": method,
        "params": params,
        "id": call_id,
    }))
    # Wait for result
    while True:
        resp = json.loads(ws.recv())
        if resp.get("msg") == "result" and resp.get("id") == call_id:
            if "error" in resp:
                raise Exception(f"DDP method error: {resp['error']}")
            return resp.get("result")
        # Skip updated/added/changed messages


def fetch_products(query: str) -> list:
    """Fetch products from Sheng Siong via DDP method call."""
    products = []
    try:
        ws = websocket.create_connection(
            DDP_URL,
            timeout=30,
            header={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )
        ddp_connect(ws)

        # Call Products.getByAllSlugs — same method the frontend uses
        # Params: filters, misc_filters, page, per_page
        filters = {
            "categoryFilter": {"slugs": []},
            "campaignPageFilter": {"slug": "", "category": {"slug": ""}},
            "shoppingListFilter": {"slug": "", "category": {"slug": ""}, "search": {"slug": ""}, "showKeptForLater": False},
            "searchFilter": {"slug": query, "category": {"slug": ""}},
            "preOrderCampaignFilter": {"slug": "", "category": {"slug": ""}},
            "ecommPromotionFilter": {"active": True, "category": {"slug": ""}},
        }
        misc_filters = {
            "brands": {"slugs": []},
            "prices": {"slugs": []},
            "countryOfOrigins": {"slugs": []},
            "dietaryHabits": {"slugs": []},
            "tags": {"slugs": []},
            "promotionTypes": {"slugs": []},
            "sortBy": {"slug": ""},
        }

        result = ddp_call(ws, "Products.getByAllSlugs", [filters, misc_filters, 1, 40])

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

        ws.close()
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
