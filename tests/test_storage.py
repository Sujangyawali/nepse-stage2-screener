import scraper.storage as storage


def test_upsert_appends_new_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)

    rows_day1 = [{"date": "2026-07-20", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000, "source": "daily_scrape"}]
    df = storage.upsert_rows("TEST", rows_day1)
    assert len(df) == 1

    rows_day2 = [{"date": "2026-07-21", "open": 104, "high": 108, "low": 103, "close": 107, "volume": 1200, "source": "daily_scrape"}]
    df = storage.upsert_rows("TEST", rows_day2)
    assert len(df) == 2
    assert list(df["close"]) == [104, 107]


def test_upsert_same_day_replaces_not_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)

    rows = [{"date": "2026-07-20", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000, "source": "daily_scrape"}]
    storage.upsert_rows("TEST", rows)

    # Re-run same day with a corrected close price (e.g. CI retry after a transient parse glitch)
    corrected_rows = [{"date": "2026-07-20", "open": 100, "high": 105, "low": 99, "close": 106, "volume": 1000, "source": "daily_scrape"}]
    df = storage.upsert_rows("TEST", corrected_rows)

    assert len(df) == 1
    assert df.iloc[0]["close"] == 106


def test_first_write_uses_clean_date_format_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)
    storage.upsert_rows("TEST", [
        {"date": "2026-07-20", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000, "source": "daily_scrape"}
    ])
    written = (tmp_path / "TEST.csv").read_text()
    assert "2026-07-20 00:00:00" not in written
    assert "2026-07-20," in written


def test_load_history_missing_symbol_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)
    df = storage.load_history("NOPE")
    assert df.empty


def test_known_symbols_lists_csv_stems(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)
    storage.upsert_rows("AAA", [{"date": "2026-07-20", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "source": "daily_scrape"}])
    storage.upsert_rows("BBB", [{"date": "2026-07-20", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "source": "daily_scrape"}])
    assert storage.known_symbols() == ["AAA", "BBB"]
