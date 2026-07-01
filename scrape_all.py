#!/usr/bin/env python3
"""Run all supermarket scrapers and aggregate results."""
import json
from datetime import datetime, timezone
from pathlib import Path

from scrapers import fairprice, shengsiong, coldstorage

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def save_snapshot(products: list, date: str):
    """Save daily snapshot and update latest data."""
    snapshot_path = DATA_DIR / f"snapshot_{date}.json"
    with open(snapshot_path, "w") as f:
        json.dump(products, f, indent=2)

    latest_path = DATA_DIR / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(products, f, indent=2)

    return snapshot_path


def update_history(products: list, date: str):
    """Update price history file with new data."""
    history_path = DATA_DIR / "price_history.json"

    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = {}

    for product in products:
        pid = product["id"]
        if pid not in history:
            history[pid] = {
                "name": product["name"],
                "supermarket": product["supermarket"],
                "category": product["category"],
                "prices": {},
            }
        history[pid]["prices"][date] = product["price"]

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)


def save_individual(store_key: str, products: list):
    """Persist per-supermarket data so it can be used as fallback on failure."""
    path = DATA_DIR / f"{store_key}.json"
    with open(path, "w") as f:
        json.dump(products, f, indent=2)


def load_fallback(store_key: str) -> list:
    """Load cached data for a supermarket when its scraper fails."""
    path = DATA_DIR / f"{store_key}.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        print(f"  ↩ Using cached data for {store_key} ({len(data)} products)")
        return data
    except Exception:
        return []


def run_scrapers() -> list:
    """Run all scrapers, falling back to cached data on failure."""
    all_products = []

    scrapers = [
        ("FairPrice", "fairprice", fairprice),
        ("Cold Storage", "coldstorage", coldstorage),
        ("Sheng Siong", "shengsiong", shengsiong),
    ]

    for name, key, scraper in scrapers:
        try:
            print(f"Scraping {name}...")
            products = scraper.scrape()
            print(f"  → {len(products)} products")

            if products:
                save_individual(key, products)
                all_products.extend(products)
            else:
                print(f"  ✗ {name} returned no products")
                fallback = load_fallback(key)
                all_products.extend(fallback)

        except Exception as e:
            print(f"  ✗ Error scraping {name}: {e}")
            fallback = load_fallback(key)
            all_products.extend(fallback)

    return all_products


def main():
    """Main entry point."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"\n=== Open Supermarket Singapore ===")
    print(f"Date: {date}\n")

    products = run_scrapers()

    if products:
        snapshot_path = save_snapshot(products, date)
        update_history(products, date)

        print(f"\nTotal products scraped: {len(products)}")
        print(f"Snapshot saved to: {snapshot_path}")

        by_store = {}
        for p in products:
            store = p["supermarket"]
            by_store[store] = by_store.get(store, 0) + 1
        for store, count in sorted(by_store.items()):
            print(f"  {store}: {count}")
    else:
        print("\nNo products scraped!")


if __name__ == "__main__":
    main()
