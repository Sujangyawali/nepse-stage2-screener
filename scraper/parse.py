from bs4 import BeautifulSoup

# Maps the page's visible column header text to our normalized field name.
# Columns not listed here (Close-LTP, Diff, Range, VWAP% etc.) are derived/redundant
# and intentionally dropped rather than stored.
HEADER_FIELD_MAP = {
    "S.No": None,
    "Symbol": "symbol",
    "Conf.": "confidence",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "LTP": "ltp",
    "Close - LTP": None,
    "Close - LTP %": None,
    "VWAP": "vwap",
    "Vol": "volume",
    "Prev. Close": "prev_close",
    "Turnover": "turnover",
    "Trans.": "transactions",
    "Diff": None,
    "Range": None,
    "Diff %": None,
    "Range %": None,
    "VWAP %": None,
    "120 Days": "ma_120",
    "180 Days": "ma_180",
    "52 Weeks High": "week52_high",
    "52 Weeks Low": "week52_low",
}


class ParseError(Exception):
    """Raised when the today-share-price table can't be located or its header changed shape."""


def _find_table(soup: BeautifulSoup):
    container = soup.select_one("div#todayshareprice_data")
    table = container.select_one("table") if container else soup.select_one("table")
    if table is None:
        raise ParseError("no table found on today-share-price page")
    return table


def _header_fields(table) -> list:
    header_cells = table.select("thead th")
    if not header_cells:
        raise ParseError("today-share-price table has no header row")
    fields = []
    for cell in header_cells:
        label = cell.get_text(strip=True)
        if label not in HEADER_FIELD_MAP:
            raise ParseError(f"unrecognized column header {label!r} — page structure may have changed")
        fields.append(HEADER_FIELD_MAP[label])
    return fields


def parse_today_rows(html: str) -> list:
    """Parse the today-share-price page into a list of raw (unnormalized, string-valued) dict rows."""
    soup = BeautifulSoup(html, "lxml")
    table = _find_table(soup)
    fields = _header_fields(table)

    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) != len(fields):
            continue
        row = {}
        for field, cell in zip(fields, cells):
            if field is None:
                continue
            if field == "symbol":
                link = cell.find("a")
                row["symbol"] = link.get_text(strip=True) if link else cell.get_text(strip=True)
                row["name"] = link.get("title", "").strip() if link else ""
            else:
                row[field] = cell.get_text(strip=True)
        if row.get("symbol"):
            rows.append(row)

    if not rows:
        raise ParseError("today-share-price table parsed to zero rows")
    return rows


def parse_as_of_date(html: str) -> str:
    """Extract the 'As of : YYYY-MM-DD' trading date shown above the table."""
    soup = BeautifulSoup(html, "lxml")
    span = soup.select_one("div#todayshareprice_data h5 span")
    if span is None:
        raise ParseError("could not find the 'As of' trading date on the page")
    return span.get_text(strip=True)
