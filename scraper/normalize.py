import math

NUMERIC_FIELDS = [
    "confidence", "open", "high", "low", "close", "ltp", "vwap", "volume",
    "prev_close", "turnover", "transactions", "ma_120", "ma_180",
    "week52_high", "week52_low",
]


def _to_number(raw: str):
    raw = (raw or "").strip().replace(",", "")
    if raw in ("", "-", "--", "N/A"):
        return math.nan
    try:
        value = float(raw)
    except ValueError:
        return math.nan
    return value


def normalize_row(raw_row: dict) -> dict:
    row = dict(raw_row)
    row["symbol"] = row["symbol"].strip().upper()
    row["name"] = row.get("name", "").strip()
    for field in NUMERIC_FIELDS:
        if field in row:
            row[field] = _to_number(row[field])
    return row


def normalize_rows(raw_rows: list) -> list:
    return [normalize_row(row) for row in raw_rows]
