# NEPSE Stage 2 Screener

A stock screener for the Nepal Stock Exchange (NEPSE) that flags equities entering **Stage 2** of
Stan Weinstein's market cycle, using Mark Minervini's Trend Template from *Trade Like a Stock
Market Wizard*.

NEPSE has no public official API, so this project scrapes public pages instead:

- A daily GitHub Actions workflow scrapes [sharesansar.com](https://www.sharesansar.com/today-share-price)'s
  end-of-day price table and appends it to a per-symbol historical dataset committed in this repo.
- A screener computes 50/150/200-session moving averages, 52-week highs/lows, and relative strength,
  and evaluates each stock against the 8-point Trend Template.
- Results are published as JSON and rendered by a static dashboard on GitHub Pages — no backend server.

See [docs/DATA_LIMITATIONS.md](docs/DATA_LIMITATIONS.md) for important caveats about data quality
(corporate-action price adjustments, backfill coverage).

## Local development

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Scrape today's prices and append to history
python -m scraper.fetch_today --dry-run

# One-time (or occasional) setup: classify each symbol's sector so the screener
# can exclude mutual funds/debentures/promoter shares, then backfill history
python -m scraper.sector_filter
python -m scraper.fetch_backfill NABIL ADBL ...   # or loop over scraper.storage.known_symbols()

# Run the full daily pipeline (scrape -> screen -> write docs/data/*.json).
# This never commits to git itself — that's a separate step the CI workflow does.
python -m scripts.run_daily

# Preview the dashboard
python -m http.server 8000 -d docs
```

## Repository layout

- `scraper/` — fetching, parsing, normalizing, and storing NEPSE price data.
- `screener/` — moving averages, Trend Template evaluation, relative strength ranking.
- `data/` — source-of-truth historical CSVs (one file per symbol) and symbol metadata.
- `docs/` — GitHub Pages site (served from `main:/docs`) and the JSON data it reads.
- `scripts/run_daily.py` — orchestrates scrape → screen → publish, used by CI and locally.
- `.github/workflows/` — scheduled scraping/screening automation.
