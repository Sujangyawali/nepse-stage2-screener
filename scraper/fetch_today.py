import time

import requests

from scraper.config import REQUEST_HEADERS, REQUEST_TIMEOUT, TODAY_PRICE_URL


class FetchError(Exception):
    """Raised when the today-share-price page can't be fetched or looks malformed."""


def fetch_today_html(retries: int = 3, backoff_seconds: float = 2.0) -> str:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                TODAY_PRICE_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            html = response.text
            if "todayshareprice_data" not in html:
                raise FetchError(
                    "today-share-price response is missing the expected table container "
                    "— page structure may have changed"
                )
            return html
        except (requests.RequestException, FetchError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise FetchError(f"failed to fetch {TODAY_PRICE_URL} after {retries} attempts") from last_exc


if __name__ == "__main__":
    import sys

    html = fetch_today_html()
    if "--dry-run" in sys.argv:
        from scraper.parse import parse_today_rows

        rows = parse_today_rows(html)
        print(f"parsed {len(rows)} rows")
        for row in rows[:5]:
            print(row)
    else:
        print(html)
