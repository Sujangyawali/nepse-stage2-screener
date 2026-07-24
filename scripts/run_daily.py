"""
Orchestrates one full pipeline run: scrape today's prices -> append to history ->
run the screener -> publish docs/data/*.json. Used by both CI (.github/workflows/
daily_scrape.yml) and local development.

Distinguishes two outcomes deliberately:
  - No new trading session yet (as_of date unchanged since the last run): a clean,
    expected no-op. Exits 0 without touching history or docs/data.
  - Any scrape/parse/screen failure: propagates as a non-zero exit so CI goes red.
    Relying on "no git diff" alone to detect problems would silently mask a real
    break on a day that happens to legitimately produce no new row.
"""
import argparse
import json
import sys
from datetime import datetime

from scraper.config import LAST_RUN_PATH, TIMEZONE
from scraper.fetch_today import fetch_today_html
from scraper.normalize import normalize_rows
from scraper.parse import parse_as_of_date, parse_today_rows
from scraper.storage import upsert_rows
from screener.build_output import run as run_screener


def _read_last_trading_date():
    if not LAST_RUN_PATH.exists():
        return None
    return json.loads(LAST_RUN_PATH.read_text()).get("last_trading_date")


def _write_last_run(as_of_date: str):
    LAST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(json.dumps({
        "last_trading_date": as_of_date,
        "run_at": datetime.now(TIMEZONE).isoformat(),
    }, indent=2))


def main(write_history_for_all: bool = False) -> int:
    html = fetch_today_html()
    as_of_date = parse_as_of_date(html)

    last_trading_date = _read_last_trading_date()
    if last_trading_date == as_of_date:
        print(f"no new trading session (as_of={as_of_date} already processed) — skipping")
        return 0

    raw_rows = parse_today_rows(html)
    rows = normalize_rows(raw_rows)

    for row in rows:
        upsert_rows(row["symbol"], [{
            "date": as_of_date,
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "source": "daily_scrape",
        }])

    print(f"appended {len(rows)} symbol rows for {as_of_date}")

    result = run_screener(write_history_for_all=write_history_for_all)
    print(
        f"screener: universe_size={result['universe_size']} "
        f"candidates_count={result['candidates_count']}"
    )

    _write_last_run(as_of_date)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape today's prices, update history, and rebuild docs/data/*.json. "
        "Never commits to git itself — that's handled by the CI workflow."
    )
    parser.add_argument("--all-history", action="store_true", help="write chart history JSON for every equity, not just candidates")
    args = parser.parse_args()
    sys.exit(main(write_history_for_all=args.all_history))
