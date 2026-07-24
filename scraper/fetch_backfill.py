"""
One-time (or occasional) historical backfill using sharesansar's own TradingView
UDF-compatible chart datafeed (the same one that powers the "Charts" tab on each
company page: https://www.sharesansar.com/company/<symbol>).

Confirmed by direct testing (see plan spike):
  GET https://www.sharesansar.com/company-chart/history
      ?symbol=<SYMBOL>&resolution=D&from=<unix>&to=<unix>&countback=<n>
  -> {"t": [...], "o": [...], "h": [...], "l": [...], "c": [...], "v": [...], "s": "ok"}

No auth/session/CSRF is required. The `countback` param is mandatory — omitting it makes
the server return {"s": "no_data"} regardless of from/to. The server also appears to ignore
`from`/`to` as a lower/upper bound and simply returns as much history as it has (observed:
~320 trading sessions back to ~2025-02-27), so `countback` is set generously and the full
returned range is used as-is.
"""
import time
from datetime import datetime, timezone

import requests

from scraper.config import HISTORY_COUNTBACK, HISTORY_URL, REQUEST_HEADERS, REQUEST_TIMEOUT


class BackfillError(Exception):
    pass


def fetch_history_bars(symbol: str, retries: int = 3, backoff_seconds: float = 1.5) -> list:
    now = int(time.time())
    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": 0,
        "to": now,
        "countback": HISTORY_COUNTBACK,
    }
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                HISTORY_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("s") != "ok":
                return []
            rows = []
            for t, o, h, l, c, v in zip(
                payload["t"], payload["o"], payload["h"], payload["l"], payload["c"], payload["v"]
            ):
                date = datetime.fromtimestamp(int(t), tz=timezone.utc).date().isoformat()
                rows.append({
                    "date": date,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                    "source": "backfill_api",
                })
            return rows
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise BackfillError(f"failed to fetch history for {symbol} after {retries} attempts") from last_exc


if __name__ == "__main__":
    import sys

    from scraper.storage import upsert_rows

    symbols = sys.argv[1:]
    if not symbols:
        print("usage: python -m scraper.fetch_backfill SYMBOL [SYMBOL ...]")
        raise SystemExit(1)

    for symbol in symbols:
        bars = fetch_history_bars(symbol)
        if not bars:
            print(f"{symbol}: no data")
            continue
        df = upsert_rows(symbol, bars)
        print(f"{symbol}: {len(bars)} bars fetched, {len(df)} rows in history now "
              f"({df.iloc[0]['date']:%Y-%m-%d} to {df.iloc[-1]['date']:%Y-%m-%d})")
        time.sleep(0.5)
