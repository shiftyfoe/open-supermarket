# Open Supermarket Singapore

Aggregates prices from Singapore's major supermarkets and tracks price changes over time.

## Supermarkets Tracked
- FairPrice
- Sheng Siong
- Cold Storage
- Giant

## Features
- Daily automated price scraping
- Historical price tracking
- Interactive price comparison charts
- GitHub Pages visualization

## Setup

### GitHub Secrets
Add these secrets to your repository (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `GIANT_ALGOLIA_APP_ID` | Algolia app ID from giant.sg |
| `GIANT_ALGOLIA_API_KEY` | Algolia API key from giant.sg |

### Local Development
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

## Data
Product and price data is stored in `data/` as JSON files. Historical data is committed daily via GitHub Actions.

## Visualization
View the live dashboard at: https://shiftyfoe.github.io/open-supermarket/
