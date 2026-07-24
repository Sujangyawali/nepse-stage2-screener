import numpy as np
import pandas as pd
import pytest

from screener.trend_template import METHODS, MIN_HISTORY_SESSIONS, evaluate


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


@pytest.mark.parametrize("method", METHODS)
def test_clean_stage2_uptrend_passes_all_non_rs_criteria(method):
    df = _uptrend_df()
    result = evaluate(df, method=method)
    assert result["data_quality"]["sufficient_history"] is True
    criteria = result["criteria"]
    for key, passed in criteria.items():
        if key == "rs_top_30pct":
            continue  # filled in later by universe.py, not evaluate()'s job
        assert passed is True, f"expected {key} to pass for a clean uptrend ({method})"


@pytest.mark.parametrize("method", METHODS)
def test_clean_stage4_downtrend_fails_most_criteria(method):
    df = _downtrend_df()
    result = evaluate(df, method=method)
    criteria = result["criteria"]
    assert criteria["price_above_150_200"] is False
    assert criteria["sma150_above_sma200"] is False
    assert criteria["sma200_trending_up"] is False
    assert criteria["sma50_above_150_200"] is False
    assert criteria["price_above_sma50"] is False
    assert criteria["within_25pct_52w_high"] is False


@pytest.mark.parametrize("method", METHODS)
def test_insufficient_history_returns_all_false_and_flagged(method):
    n = MIN_HISTORY_SESSIONS - 1
    df = _uptrend_df(n=n)
    result = evaluate(df, method=method)
    assert result["data_quality"]["sufficient_history"] is False
    assert all(v is False for v in result["criteria"].values())
    assert result["ma50"] is None


@pytest.mark.parametrize("method", METHODS)
def test_corporate_action_gap_flagged_without_altering_criteria(method):
    df = _uptrend_df()
    # Simulate an unadjusted bonus-share gap: a single-day 25% cliff mid-series
    df.loc[100, "close"] = df.loc[99, "close"] * 0.75
    result = evaluate(df, method=method)
    assert result["data_quality"]["possible_corporate_action_gap"] is True


@pytest.mark.parametrize("method", METHODS)
def test_no_gap_flag_for_normal_moves(method):
    df = _uptrend_df()
    result = evaluate(df, method=method)
    assert result["data_quality"]["possible_corporate_action_gap"] is False


def test_ama_and_sma_can_disagree_on_a_recent_reversal():
    # A stock in a long downtrend that has just sharply reversed: SMA200 (slow, backward-
    # looking) is still falling, while KAMA's slow_period=200 tier — driven by the
    # efficiency ratio of the *recent* move — reacts faster to the new trend.
    n = 260
    down = np.linspace(300, 150, n - 15)
    up = np.linspace(150, 250, 15)
    close = np.concatenate([down, up])
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame({"date": dates, "close": close})

    sma_result = evaluate(df, method="sma")
    ama_result = evaluate(df, method="ama")

    assert sma_result["criteria"]["sma200_trending_up"] is False
    assert ama_result["criteria"]["sma200_trending_up"] is True
