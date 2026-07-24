import pandas as pd

from scraper.config import HISTORY_CSV_COLUMNS, HISTORY_DIR


class InvalidSymbolError(Exception):
    """Raised for a symbol that isn't safe to use as a filename.

    Some NEPSE debenture/bond instruments encode a Nepali fiscal-year range directly in
    their symbol (e.g. "NICD83/84"), which would otherwise be silently misread as a nested
    path. These instruments are excluded from the equity screener anyway, so callers should
    filter to classified equity symbols before calling upsert_rows — this is a defensive
    backstop, not the primary filter.
    """


def _history_path(symbol: str):
    if "/" in symbol or "\\" in symbol or symbol in (".", ".."):
        raise InvalidSymbolError(f"symbol {symbol!r} is not safe to use as a filename")
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR / f"{symbol}.csv"


def load_history(symbol: str) -> pd.DataFrame:
    path = _history_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=HISTORY_CSV_COLUMNS)
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def upsert_rows(symbol: str, new_rows: list) -> pd.DataFrame:
    """
    new_rows: list of dicts with keys date (str 'YYYY-MM-DD' or Timestamp), open, high, low,
      close, volume, source. Rows with a date already present are replaced (safe re-run same
      day / CI retries); new dates are appended. Result is sorted and de-duplicated by date.
    """
    existing = load_history(symbol)
    incoming = pd.DataFrame(new_rows)
    if incoming.empty:
        return existing
    incoming["date"] = pd.to_datetime(incoming["date"])

    combined = pd.concat([existing, incoming], ignore_index=True)
    # Concatenating an empty (object-dtype) `existing` frame with a datetime64 `incoming`
    # frame can upcast "date" back to object dtype, which silently defeats to_csv's
    # date_format below (it only formats real datetime64 columns) and writes a spurious
    # " 00:00:00" time component. Force it back explicitly so first-time writes and later
    # writes are byte-for-byte consistent.
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.drop_duplicates(subset="date", keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    combined = combined[HISTORY_CSV_COLUMNS]

    path = _history_path(symbol)
    combined.to_csv(path, index=False, date_format="%Y-%m-%d")
    return combined


def known_symbols() -> list:
    if not HISTORY_DIR.exists():
        return []
    return sorted(p.stem for p in HISTORY_DIR.glob("*.csv"))
