"""Sheng Siong online scraper using Meteor DDP over HTTP long-polling.

Sheng Siong is a Meteor.js SPA behind Incapsula CDN.
Incapsula blocks WebSocket handshakes from CI, but HTTP POST to the
SockJS XHR transport may work since it's regular HTTP.
"""
import json
import re
import requests
import random
import string
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/plain",
    "Origin": SHENGSIONG_BASE,
    "Referer": f"{SHENGSIONG_BASE}/",
}


def ddp_session():
    """Establish a SockJS XHR session and return (base_url, session_id)."""
    server_id = str(random.randint(100, 999))
    session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    base = f"{SHENGSIONG_BASE}/sockjs/{server_id}/{session_id}"
    return base, session_id


def ddp_connect(base_url):
    """Send DDP connect via SockJS XHR transport."""
    # SockJS XHR transport: POST to /xhr endpoint
    connect_msg = json.dumps({"msg": "connect", "version": "1", "support": ["1", "pre2", "pre1"]})
    payload = f'["{connect_msg}"]'
    resp = requests.post(f"{base_url}/xhr", headers=HEADERS, data=payload, timeout=30)
    resp.raise_for_status()
    # Response should contain "o" (open) then the connect result
    return resp.text


def ddp_call(base_url, method, params, call_id=None):
    """Call a Meteor method via SockJS XHR."""
    if call_id is None:
        call_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    method_msg = json.dumps({
        "msg": "method",
        "method": method,
        "params": params,
        "id": call_id,
    })
    payload = f'["{method_msg}"]'
    resp = requests.post(f"{base_url}/xhr", headers=HEADERS, data=payload, timeout=30)
    resp.raise_for_status()

    # Parse SockJS response — may contain multiple frames
    text = resp.text
    # SockJS frames are JSON arrays; each element is a message
    # The response might look like: 'a["{...}"]'
    if text.startswith('a'):
        text = text[1:]

    try:
        frames = json.loads(text)
        for frame in frames:
            msg = json.loads(frame)
            if msg.get("msg") == "result" and msg.get("id") == call_id:
                if "error" in msg:
                    raise Exception(f"DDP error: {msg['error']}")
                return msg.get("result")
    except json.JSONDecodeError:
        pass

    return None


def fetch_products(query: str) -> list:
    """Fetch products from Sheng Siong via DDP over HTTP."""
    products = []
    try:
        base_url, _ = ddp_session()

        # Connect
        connect_resp = ddp_connect(base_url)
        print(f"[ShengSiong] {query}: connect response: {connect_resp[:100]}")

        # Call Products.getByAllSlugs
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

        result = ddp_call(base_url, "Products.getByAllSlugs", [filters, misc_filters, 1, 40])

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

        print(f"[ShengSiong] {query}: got {len(products)} products")
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
