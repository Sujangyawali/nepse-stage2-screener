"""
Builds/refreshes data/meta/symbols.json: the symbol -> {name, sector, is_equity} mapping
used to exclude mutual funds, debentures, preference shares, and promoter shares from the
screening universe.

Sector isn't exposed on the today-share-price table itself, and the sector-filter dropdown
on that page is a JS/CSRF-protected POST (not a plain scrapeable GET). It IS exposed as a
hidden `<div id="sector">` on each company's own page (e.g. sharesansar.com/company/nabil),
so this module fetches that page once per symbol. Sector rarely changes, so this is meant to
be run occasionally (e.g. monthly via workflow_dispatch), not on every daily scrape — the
daily pipeline only *reads* the cached data/meta/symbols.json.
"""
import json
import time

import requests
from bs4 import BeautifulSoup

from scraper.config import (
    COMPANY_PAGE_URL,
    EXCLUDED_SECTORS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SYMBOLS_META_PATH,
)


class CompanyPageError(Exception):
    pass


def fetch_company_sector(symbol: str, retries: int = 3, backoff_seconds: float = 1.5) -> dict:
    url = COMPANY_PAGE_URL.format(slug=symbol.lower())
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            sector_div = soup.select_one("#sector")
            if sector_div is None:
                raise CompanyPageError(f"no #sector element found for {symbol} at {url}")
            return {"sector": sector_div.get_text(strip=True)}
        except (requests.RequestException, CompanyPageError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise CompanyPageError(f"failed to fetch sector for {symbol} after {retries} attempts") from last_exc


def is_equity_sector(sector: str) -> bool:
    return sector not in EXCLUDED_SECTORS


def build_symbols_meta(rows: list, delay_seconds: float = 0.5, existing: dict | None = None) -> dict:
    """
    rows: normalized today-share-price rows (each has 'symbol' and 'name').
    existing: previously saved symbols.json contents, reused to skip re-fetching symbols
      whose sector is already known (sector reclassification is rare).
    """
    meta = dict(existing or {})
    for row in rows:
        symbol = row["symbol"]
        if symbol in meta and meta[symbol].get("sector"):
            continue
        try:
            info = fetch_company_sector(symbol)
        except CompanyPageError as exc:
            print(f"warning: could not classify {symbol}: {exc}")
            continue
        sector = info["sector"]
        meta[symbol] = {
            "name": row.get("name", ""),
            "sector": sector,
            "is_equity": is_equity_sector(sector),
        }
        time.sleep(delay_seconds)
    return meta


def load_symbols_meta() -> dict:
    if not SYMBOLS_META_PATH.exists():
        return {}
    return json.loads(SYMBOLS_META_PATH.read_text())


def save_symbols_meta(meta: dict) -> None:
    SYMBOLS_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYMBOLS_META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    from scraper.fetch_today import fetch_today_html
    from scraper.normalize import normalize_rows
    from scraper.parse import parse_today_rows

    html = fetch_today_html()
    today_rows = normalize_rows(parse_today_rows(html))
    existing_meta = load_symbols_meta()
    updated_meta = build_symbols_meta(today_rows, existing=existing_meta)
    save_symbols_meta(updated_meta)
    equity_count = sum(1 for v in updated_meta.values() if v["is_equity"])
    print(f"classified {len(updated_meta)} symbols ({equity_count} equities) -> {SYMBOLS_META_PATH}")
