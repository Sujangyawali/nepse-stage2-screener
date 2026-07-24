from pathlib import Path

import pytest

from scraper.normalize import normalize_rows
from scraper.parse import ParseError, parse_as_of_date, parse_today_rows

FIXTURE = (Path(__file__).parent / "fixtures" / "sample_today_page.html").read_text()


def test_parses_expected_row_count():
    rows = parse_today_rows(FIXTURE)
    assert len(rows) == 3


def test_extracts_symbol_and_name():
    rows = parse_today_rows(FIXTURE)
    assert rows[0]["symbol"] == "ACLBSL"
    assert rows[0]["name"] == "Aarambha Chautari Laghubitta Bittiya Sanstha Limited"
    assert rows[1]["symbol"] == "NABIL"


def test_raises_on_empty_html():
    with pytest.raises(ParseError):
        parse_today_rows("<html><body>no table here</body></html>")


def test_normalize_strips_commas_and_coerces_numeric():
    rows = parse_today_rows(FIXTURE)
    normalized = normalize_rows(rows)
    nabil = next(r for r in normalized if r["symbol"] == "NABIL")
    assert nabil["turnover"] == 22102345.00
    assert nabil["close"] == 550.00
    assert nabil["volume"] == 40281.00


def test_normalize_handles_dash_as_missing():
    rows = parse_today_rows(FIXTURE)
    normalized = normalize_rows(rows)
    xyzmf = next(r for r in normalized if r["symbol"] == "XYZMF")
    assert xyzmf["confidence"] != xyzmf["confidence"]  # NaN
    assert xyzmf["turnover"] != xyzmf["turnover"]  # NaN


def test_parse_as_of_date():
    assert parse_as_of_date(FIXTURE) == "2026-07-23"
