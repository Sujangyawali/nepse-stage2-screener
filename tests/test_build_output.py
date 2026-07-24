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
    assert series[250]["sma200"] is not None
    assert series[250]["ama200"] is not None


def _synthetic_history(n, kind, seed):
    rng = np.random.default_rng(seed)
    if kind == "uptrend":
        base = np.linspace(100, 250, n)
    elif kind == "reversal":
        # Long downtrend that sharply reverses in the last few weeks — SMA200 (slow,
        # backward-looking) stays down; AMA reacts to the recent efficient move upward.
        base = np.concatenate([np.linspace(300, 150, n - 15), np.linspace(150, 260, 15)])
    else:
        raise ValueError(kind)
    close = base + rng.normal(0, 0.5, n)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "date": dates, "open": close, "high": close, "low": close, "close": close,
        "volume": 1000, "source": "daily_scrape",
    })


def test_sma_and_ama_candidate_lists_are_independent(tmp_path, monkeypatch):
    import screener.build_output as build_output

    monkeypatch.setattr(storage, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(
        build_output, "load_symbols_meta",
        lambda: {"UPTREND": {"name": "Uptrend Co", "sector": "Others", "is_equity": True},
                 "REVERSAL": {"name": "Reversal Co", "sector": "Others", "is_equity": True}},
    )
    monkeypatch.setattr(build_output, "known_symbols", lambda: ["REVERSAL", "UPTREND"])

    storage.upsert_rows("UPTREND", _synthetic_history(260, "uptrend", seed=1).to_dict("records"))
    storage.upsert_rows("REVERSAL", _synthetic_history(260, "reversal", seed=2).to_dict("records"))

    candidates, _ = build_candidates()

    sma_by_symbol = {s["symbol"]: s for s in candidates["sma"]["stocks"]}
    ama_by_symbol = {s["symbol"]: s for s in candidates["ama"]["stocks"]}

    # A clean uptrend should be a candidate under both methods.
    assert sma_by_symbol["UPTREND"]["is_candidate"] is True
    assert ama_by_symbol["UPTREND"]["is_candidate"] is True
    # The recent-reversal stock's overall trend-up signal should differ by method: SMA200
    # (slow, backward-looking) still reads falling, while AMA — driven by the efficiency of
    # the *recent* move — has already turned up. This is what makes the two candidate lists
    # genuinely independent rather than just relabeled copies of each other.
    assert sma_by_symbol["REVERSAL"]["criteria"]["sma200_trending_up"] is False
    assert ama_by_symbol["REVERSAL"]["criteria"]["sma200_trending_up"] is True
