import numpy as np
import pandas as pd

import scraper.storage as storage
from screener.build_output import HISTORY_CHART_SESSIONS, build_candidates, write_history_json


def test_write_history_json_full_lookback_near_window_start():
    n = HISTORY_CHART_SESSIONS + 250  # plenty of history before the trimmed display window
    rng = np.random.default_rng(0)
    close = np.linspace(100, 300, n) + rng.normal(0, 0.5, n)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({"date": dates, "close": close})

    result = write_history_json("TEST", df)
    series = result["series"]

    assert len(series) == HISTORY_CHART_SESSIONS
    # The 250th point in a 300-point trimmed window would have no 200-window MA if MAs were
    # computed after trimming (only 250 rows of lookback available); with the full-history
    # fix it should be populated since 250 + 200 rows of real history exist before it.
    assert series[250]["ama200"] is not None
    assert set(series[-1]) == {"date", "close", "ama20", "ama50", "ama150", "ama200"}


def _synthetic_history(n, seed):
    rng = np.random.default_rng(seed)
    close = np.linspace(100, 250, n) * np.exp(rng.normal(0, 0.015, n))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "date": dates, "open": close, "high": close, "low": close, "close": close,
        "volume": 1000, "source": "daily_scrape",
    })


def test_build_candidates_single_ama_block(tmp_path, monkeypatch):
    import screener.build_output as build_output

    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(
        build_output, "load_symbols_meta",
        lambda: {"UPTREND": {"name": "Uptrend Co", "sector": "Others", "is_equity": True},
                 "SHORT": {"name": "New Listing", "sector": "Others", "is_equity": True}},
    )
    monkeypatch.setattr(build_output, "known_symbols", lambda: ["SHORT", "UPTREND"])

    storage.upsert_rows("UPTREND", _synthetic_history(300, seed=1).to_dict("records"))
    storage.upsert_rows("SHORT", _synthetic_history(150, seed=2).to_dict("records"))

    candidates, _ = build_candidates()

    assert "sma" not in candidates and "ama" not in candidates
    assert candidates["universe_size"] == 2
    by_symbol = {s["symbol"]: s for s in candidates["stocks"]}

    up = by_symbol["UPTREND"]
    for key in ("ma20", "ma50", "ma150", "ma200"):
        assert up[key] is not None
    assert up["criteria"]["ma200_trending_up"] is True
    assert up["criteria"]["price_above_150_200"] is True

    short = by_symbol["SHORT"]
    assert short["data_quality"]["sufficient_history"] is False
    assert short["is_candidate"] is False
