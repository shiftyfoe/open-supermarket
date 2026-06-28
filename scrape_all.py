#!/usr/bin/env python3
"""Run all supermarket scrapers and aggregate results."""
import json
import os
from datetime import datetime
from pathlib import Path

from scrapers import fairprice, shengsiong, coldstorage, giant

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def save_snapshot(products: list, date: str):
    """Save daily snapshot and update latest data."""
    # Save dated snapshot
    snapshot_path = DATA_DIR / f"snapshot_{date}.json"
    with open(snapshot_path, "w") as f:
        json.dump(products, f, indent=2)

    # Save latest data
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


def run_scrapers() -> list:
    """Run all scrapers and combine results."""
    all_products = []

    scrapers = [
        ("FairPrice", fairprice),
        ("Cold Storage", coldstorage),
        ("Sheng Siong", shengsiong),
        ("Giant", giant),
    ]

    for name, scraper in scrapers:
        try:
            print(f"Scraping {name}...")
            products = scraper.scrape()
            print(f"  → {len(products)} products")
            all_products.extend(products)
        except Exception as e:
            print(f"  ✗ Error: {e}")

    return all_products


def main():
    """Main entry point."""
    date = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n=== Open Supermarket Singapore ===")
    print(f"Date: {date}\n")

    products = run_scrapers()

    if products:
        snapshot_path = save_snapshot(products, date)
        update_history(products, date)

        print(f"\nTotal products scraped: {len(products)}")
        print(f"Snapshot saved to: {snapshot_path}")

        # Print summary by supermarket
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
