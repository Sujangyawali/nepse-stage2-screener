import numpy as np
import pandas as pd

from screener.trend_template import MIN_HISTORY_SESSIONS, evaluate


def _uptrend_df(n=260, start=100.0, end=250.0, noise=0.5, seed=1):
    rng = np.random.default_rng(seed)
    base = np.linspace(start, end, n)
    close = base + rng.normal(0, noise, n)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({"date": dates, "close": close})


def _downtrend_df(n=260, start=300.0, end=150.0, noise=0.5, seed=2):
    rng = np.random.default_rng(seed)
    base = np.linspace(start, end, n)
    close = base + rng.normal(0, noise, n)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({"date": dates, "close": close})


def test_clean_stage2_uptrend_passes_all_non_rs_criteria():
    df = _uptrend_df()
    result = evaluate(df)
    assert result["data_quality"]["sufficient_history"] is True
    criteria = result["criteria"]
    for key, passed in criteria.items():
        if key == "rs_top_30pct":
            continue  # filled in later by universe.py, not evaluate()'s job
        assert passed is True, f"expected {key} to pass for a clean uptrend"


def test_clean_stage4_downtrend_fails_most_criteria():
    df = _downtrend_df()
    result = evaluate(df)
    criteria = result["criteria"]
    assert criteria["price_above_150_200"] is False
    assert criteria["sma150_above_sma200"] is False
    assert criteria["sma200_trending_up"] is False
    assert criteria["sma50_above_150_200"] is False
    assert criteria["price_above_sma50"] is False
    assert criteria["within_25pct_52w_high"] is False


def test_insufficient_history_returns_all_false_and_flagged():
    n = MIN_HISTORY_SESSIONS - 1
    df = _uptrend_df(n=n)
    result = evaluate(df)
    assert result["data_quality"]["sufficient_history"] is False
    assert all(v is False for v in result["criteria"].values())
    assert result["sma50"] is None


def test_corporate_action_gap_flagged_without_altering_criteria():
    df = _uptrend_df()
    # Simulate an unadjusted bonus-share gap: a single-day 25% cliff mid-series
    df.loc[100, "close"] = df.loc[99, "close"] * 0.75
    result = evaluate(df)
    assert result["data_quality"]["possible_corporate_action_gap"] is True


def test_no_gap_flag_for_normal_moves():
    df = _uptrend_df()
    result = evaluate(df)
    assert result["data_quality"]["possible_corporate_action_gap"] is False
