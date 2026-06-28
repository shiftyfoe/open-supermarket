# Open Supermarket Singapore

Aggregates prices from Singapore's major supermarkets and tracks price changes over time.

## Supermarkets Tracked
- ✅ FairPrice (121 products)
- ✅ Cold Storage (240 products)
- ⏳ Sheng Siong (coming soon)

## Features
- Daily automated price scraping
- Historical price tracking
- Interactive price comparison charts
- GitHub Pages visualization

## Setup

### Local Development
```bash
pip install -r requirements.txt
python scrape_all.py
```

## Data
Product and price data is stored in `data/` as JSON files. Historical data is committed daily via GitHub Actions.

## Visualization
View the live dashboard at: https://shiftyfoe.github.io/open-supermarket/
