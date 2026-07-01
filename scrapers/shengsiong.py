"""Sheng Siong scraper using direct Meteor DDP over WebSocket.

Sheng Siong is a Meteor.js SPA behind Incapsula CDN. We bypass the
JavaScript challenge entirely by connecting directly to the DDP WebSocket
endpoint rather than rendering the page in a browser.

Fallback: Playwright-based approach (may be blocked by Incapsula on
datacenter IPs such as GitHub Actions runners).
"""
import asyncio
import json
import random
import re
import string
import time
from datetime import datetime, timezone

SHENGSIONG_BASE = "https://www.shengsiong.com.sg"
SHENGSIONG_WS = "wss://www.shengsiong.com.sg"

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

REQUEST_DELAY = 2.0


# ---------------------------------------------------------------------------
# DDP / WebSocket approach (primary – no browser required)
# ---------------------------------------------------------------------------

def _build_ddp_filters(query: str) -> tuple:
    """Return the (filters, misc) dicts expected by Products.getByAllSlugs."""
    filters = {
        "categoryFilter": {"slugs": []},
        "campaignPageFilter": {"slug": "", "category": {"slug": ""}},
        "shoppingListFilter": {
            "slug": "", "category": {"slug": ""},
            "search": {"slug": ""}, "showKeptForLater": False,
        },
        "searchFilter": {"slug": query, "category": {"slug": ""}},
        "preOrderCampaignFilter": {"slug": "", "category": {"slug": ""}},
        "ecommPromotionFilter": {"active": True, "category": {"slug": ""}},
    }
    misc = {
        "brands": {"slugs": []},
        "prices": {"slugs": []},
        "countryOfOrigins": {"slugs": []},
        "dietaryHabits": {"slugs": []},
        "tags": {"slugs": []},
        "promotionTypes": {"slugs": []},
        "sortBy": {"slug": ""},
    }
    return filters, misc


def _parse_sockjs(raw: str) -> list:
    """Extract the list of DDP JSON strings from a SockJS frame."""
    # SockJS sends: a["<escaped json>", ...]
    if not raw or raw[0] not in ("a", "o", "h", "c"):
        return []
    if raw[0] != "a":
        return []
    try:
        return json.loads(raw[1:])
    except json.JSONDecodeError:
        return []


async def _ddp_fetch(query: str, timeout: float = 20.0) -> list:
    """Open a DDP WebSocket to Sheng Siong and call Products.getByAllSlugs."""
    try:
        import websockets  # type: ignore[import-untyped]
    except ImportError:
        return []

    server_id = str(random.randint(100, 999))
    session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    ws_url = f"{SHENGSIONG_WS}/sockjs/{server_id}/{session_id}/websocket"

    headers = {
        "Origin": SHENGSIONG_BASE,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    filters, misc = _build_ddp_filters(query)
    call_id = "1"

    try:
        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            open_timeout=timeout,
            ping_interval=None,
        ) as ws:
            # SockJS open frame
            frame = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if frame != "o":
                print(f"[ShengSiong] Unexpected SockJS frame: {frame!r}")
                return []

            # DDP connect
            await ws.send(
                json.dumps([json.dumps({"msg": "connect", "version": "1", "support": ["1"]})])
            )

            # Wait for DDP connected confirmation
            connected = False
            while not connected:
                frame = await asyncio.wait_for(ws.recv(), timeout=timeout)
                for msg_str in _parse_sockjs(frame):
                    try:
                        msg = json.loads(msg_str)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("msg") == "connected":
                        connected = True
                        break

            if not connected:
                return []

            # DDP method call
            method_payload = json.dumps({
                "msg": "method",
                "method": "Products.getByAllSlugs",
                "params": [filters, misc, 1, 40],
                "id": call_id,
            })
            await ws.send(json.dumps([method_payload]))

            # Collect result
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                frame = await asyncio.wait_for(ws.recv(), timeout=remaining)
                for msg_str in _parse_sockjs(frame):
                    try:
                        msg = json.loads(msg_str)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("msg") == "result" and msg.get("id") == call_id:
                        result = msg.get("result", [])
                        if isinstance(result, list):
                            print(f"[ShengSiong] DDP {query}: {len(result)} products")
                            return result
                        return []

    except Exception as e:
        print(f"[ShengSiong] DDP error for {query!r}: {e}")

    return []


def fetch_via_ddp(categories: list) -> list:
    """Fetch all categories using direct DDP WebSocket calls."""

    async def _run():
        products = []
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            products.extend(await _ddp_fetch(cat))
        return products

    try:
        return asyncio.run(_run())
    except Exception as e:
        print(f"[ShengSiong] DDP batch error: {e}")
        return []


# ---------------------------------------------------------------------------
# Playwright fallback (may be blocked on datacenter IPs)
# ---------------------------------------------------------------------------

def fetch_products_playwright(query: str, page) -> list:
    """Fetch products via Meteor.call() from a Playwright-rendered page."""
    filters, misc = _build_ddp_filters(query)

    # Pass filters as JS literal instead of rebuilding in page context
    filters_js = json.dumps(filters)
    misc_js = json.dumps(misc)

    try:
        result = page.evaluate(f"""
            async () => {{
                return new Promise((resolve, reject) => {{
                    if (typeof Meteor === 'undefined') {{
                        reject(new Error("Meteor not available"));
                        return;
                    }}
                    Meteor.call(
                        "Products.getByAllSlugs",
                        {filters_js},
                        {misc_js},
                        1, 40,
                        (err, res) => {{
                            if (err) reject(err);
                            else resolve(res);
                        }}
                    );
                }});
            }}
        """)
        if result and isinstance(result, list):
            print(f"[ShengSiong] Playwright {query}: {len(result)} products")
            return result
    except Exception as e:
        print(f"[ShengSiong] Playwright error for {query!r}: {e}")

    return []


def create_browser():
    """Create a Playwright Chromium browser with stealth settings."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    stealth = Stealth()
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-SG",
        java_script_enabled=True,
    )
    page = context.new_page()
    stealth.apply_stealth_sync(page)

    page.goto(SHENGSIONG_BASE, wait_until="domcontentloaded", timeout=30000)
    # Give Incapsula challenge time to complete (increased from 5 s)
    page.wait_for_timeout(10000)

    content_len = len(page.content())
    if content_len < 2000:
        print(f"[ShengSiong] Blocked by Incapsula ({content_len} bytes)")
        browser.close()
        p.stop()
        return None, None, None

    print(f"[ShengSiong] Playwright browser ready ({content_len} bytes)")
    return p, browser, page


def fetch_via_playwright(categories: list) -> list:
    """Fetch all categories using Playwright (fallback)."""
    playwright, browser, page = create_browser()
    if playwright is None or browser is None or page is None:
        return []

    all_products = []
    try:
        for i, cat in enumerate(categories):
            if i > 0:
                time.sleep(REQUEST_DELAY)
            all_products.extend(fetch_products_playwright(cat, page))
    finally:
        browser.close()
        playwright.stop()

    return all_products


# ---------------------------------------------------------------------------
# Shared parsing and main entry point
# ---------------------------------------------------------------------------

def parse_product(raw: dict) -> dict:
    product_id = re.sub(r"[^a-z0-9]", "_", raw.get("name", "").lower())[:30]
    price = raw.get("price", raw.get("finalPrice", 0))
    if isinstance(price, dict):
        price = price.get("amount", 0)
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0

    img = ""
    images = raw.get("images", [])
    if images and isinstance(images, list):
        img = images[0] if isinstance(images[0], str) else images[0].get("url", "")

    return {
        "id": f"ss_{product_id}",
        "supermarket": "shengsiong",
        "name": raw.get("name", ""),
        "brand": "",
        "category": raw.get("category", ""),
        "price": price,
        "original_price": price,
        "unit": "",
        "size": "",
        "image_url": img,
        "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }


def scrape() -> list:
    """Scrape all tracked categories. Try DDP first, then Playwright."""
    raw_items: list = []

    # Primary: direct DDP (no browser, no JS challenge)
    print("[ShengSiong] Trying DDP WebSocket approach...")
    try:
        __import__("websockets")
        raw_items = fetch_via_ddp(CATEGORIES)
    except ImportError:
        print("[ShengSiong] websockets not installed, skipping DDP approach")

    if not raw_items:
        print("[ShengSiong] DDP approach yielded no data, falling back to Playwright...")
        raw_items = fetch_via_playwright(CATEGORIES)

    seen_ids: set = set()
    products: list = []
    for raw in raw_items:
        parsed = parse_product(raw)
        if parsed["price"] > 0 and parsed["id"] not in seen_ids:
            seen_ids.add(parsed["id"])
            products.append(parsed)

    return products


if __name__ == "__main__":
    products = scrape()
    print(f"[ShengSiong] Scraped {len(products)} products")
    with open("data/shengsiong.json", "w") as f:
        json.dump(products, f, indent=2)
