from pathlib import Path
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Kathmandu")

TODAY_PRICE_URL = "https://www.sharesansar.com/today-share-price"
COMPANY_PAGE_URL = "https://www.sharesansar.com/company/{slug}"
HISTORY_URL = "https://www.sharesansar.com/company-chart/history"

# The history endpoint requires `countback` — without it the server returns no_data
# regardless of the from/to range. `from`/`to` are still sent for spec-compliance but
# the server appears to ignore `from` and just returns as much history as it has
# (observed: ~320 trading sessions back to ~2025-02-27), capped by whatever countback asks for.
HISTORY_COUNTBACK = 5000

REQUEST_TIMEOUT = 20
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
META_DIR = DATA_DIR / "meta"
SYMBOLS_META_PATH = META_DIR / "symbols.json"
LAST_RUN_PATH = META_DIR / "last_run.json"
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"

# Sector taxonomy scraped from the "Select Sector" filter on /today-share-price.
# Sectors NOT in this set are excluded from the equity screening universe.
EXCLUDED_SECTORS = {
    "Corporate Debentures",
    "Government Bonds",
    "Mutual Fund",
    "Preference Share",
    "Promoter Share",
}

HISTORY_CSV_COLUMNS = [
    "date", "open", "high", "low", "close", "volume", "source",
]
