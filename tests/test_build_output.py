import pytest
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


def test_write_history_json_includes_ohlcv_for_candlesticks():
    df = _synthetic_history(250, seed=3)
    df["volume"] = np.arange(250, dtype=float)
    point = write_history_json("TEST", df)["series"][-1]

    assert {"open", "high", "low", "close", "volume"} <= set(point)
    assert point["volume"] == 249.0
    # values are rounded so the published JSON stays compact
    assert point["ama200"] == round(point["ama200"], 4)


def test_charts_published_for_top_n_plus_all_candidates():
    from screener.build_output import symbols_to_publish_charts

    stocks = [{"symbol": f"S{i}", "is_candidate": i < 3} for i in range(30)]
    stocks[25]["is_candidate"] = True  # a candidate ranked outside the top N still gets a chart

    published = symbols_to_publish_charts(stocks, top_n=20)

    assert published == {f"S{i}" for i in range(20)} | {"S25"}


def test_rank_key_orders_by_score_then_rs_then_52w_high():
    from screener.build_output import _rank_key

    stocks = [
        {"symbol": "LOW_SCORE", "score": 7, "rs_percentile": 99.0, "pct_from_52w_high": 0.0},
        {"symbol": "FAR_HIGH", "score": 8, "rs_percentile": 90.0, "pct_from_52w_high": 20.0},
        {"symbol": "NEAR_HIGH", "score": 8, "rs_percentile": 90.0, "pct_from_52w_high": 2.0},
        {"symbol": "TOP_RS", "score": 8, "rs_percentile": 95.0, "pct_from_52w_high": 10.0},
        {"symbol": "NO_RS", "score": 8, "rs_percentile": None, "pct_from_52w_high": None},
    ]
    ordered = [s["symbol"] for s in sorted(stocks, key=_rank_key)]

    assert ordered == ["TOP_RS", "NEAR_HIGH", "FAR_HIGH", "NO_RS", "LOW_SCORE"]


def _session_history(close, volume, transactions, turnover, last_date="2026-11-27"):
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-11-26", last_date]),
        "close": [close * 0.9, close],
        "volume": [1.0, volume],
        "transactions": [None, transactions],
        "turnover": [None, turnover],
    })


def test_market_activity_merges_top_lists_without_duplicates():
    from screener.build_output import build_market_activity

    histories = {
        # ALL tops every list -> must appear exactly once, tagged with all three
        "ALL": _session_history(100, volume=900, transactions=90, turnover=9000),
        "VOL": _session_history(100, volume=800, transactions=1, turnover=1),
        "TX": _session_history(100, volume=1, transactions=80, turnover=2),
        "TURN": _session_history(100, volume=2, transactions=2, turnover=8000),
        "QUIET": _session_history(100, volume=0.5, transactions=0.5, turnover=0.5),
        "STALE": _session_history(100, volume=10_000, transactions=10_000, turnover=10_000,
                                  last_date="2026-11-20"),
    }
    stocks = [{"symbol": s, "name": s, "sector": "X", "rank": i + 1, "score": 8, "is_candidate": False}
              for i, s in enumerate(histories)]

    result = build_market_activity(histories, stocks, "2026-11-27", top_n=2)
    by_symbol = {s["symbol"]: s for s in result["stocks"]}

    assert [s["symbol"] for s in result["stocks"]].count("ALL") == 1
    assert by_symbol["ALL"]["categories"] == ["volume", "transactions", "turnover"]
    assert by_symbol["ALL"]["ranks"] == {"volume": 1, "transactions": 1, "turnover": 1}
    assert result["stocks"][0]["symbol"] == "ALL"  # most lists first
    assert by_symbol["VOL"]["categories"] == ["volume"]
    assert by_symbol["TX"]["categories"] == ["transactions"]
    assert by_symbol["TURN"]["categories"] == ["turnover"]
    assert "QUIET" not in by_symbol  # outside every top 2
    assert "STALE" not in by_symbol  # didn't trade in the latest session
    assert by_symbol["ALL"]["change_pct"] == pytest.approx(11.11, abs=0.01)


def test_market_activity_tolerates_history_without_turnover_columns():
    from screener.build_output import build_market_activity

    df = pd.DataFrame({"date": pd.to_datetime(["2026-11-26", "2026-11-27"]),
                       "close": [10.0, 11.0], "volume": [5.0, 6.0]})
    result = build_market_activity({"OLD": df}, [], "2026-11-27")

    assert result["stocks"][0]["categories"] == ["volume"]
