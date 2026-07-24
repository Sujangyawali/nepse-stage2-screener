import pandas as pd

from scraper.config import HISTORY_CSV_COLUMNS, HISTORY_DIR


def _history_path(symbol: str):
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
