import numpy as np
import pandas as pd

import math
from pathlib import Path

import pytest

from screener.indicators import adaptive_ma, is_trending_up, week52_high_low


def test_is_trending_up_true_when_rising():
    series = pd.Series(range(1, 31), dtype=float)  # 1..30, monotonic
    assert is_trending_up(series, lookback=20) is True


def test_is_trending_up_false_when_falling():
    series = pd.Series(range(30, 0, -1), dtype=float)
    assert is_trending_up(series, lookback=20) is False


def test_is_trending_up_none_when_insufficient_history():
    series = pd.Series(range(1, 10), dtype=float)
    assert is_trending_up(series, lookback=20) is None


def test_week52_high_low_uses_trailing_window():
    close = pd.Series([50] * 10 + [200] + [100] * 224)  # spike buried far in the past
    high, low = week52_high_low(close, sessions=235)
    # window of last 235 covers the tail of the 50s, the 200 spike, and the 100s
    assert high == 200
    assert low == 50


def test_adaptive_ma_nan_until_period_bars_of_history():
    series = pd.Series([100.0, 110.0, 99.0, 108.9, 104.0])
    result = adaptive_ma(series, 2)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].notna().all()


def test_adaptive_ma_matches_hand_computed_formula():
    # NepseAlpha / TradingView "Moving Average Adaptive", period 2, worked by hand:
    # the running value is seeded with the previous close (110), then
    #   alpha = 0.1 * |ln(c / c[2])| / (popstdev(last 2 log returns) * sqrt(2))
    series = pd.Series([100.0, 110.0, 99.0])
    r1, r2 = math.log(110 / 100), math.log(99 / 110)
    sigma = abs(r1 - r2) / 2  # population stdev of two values
    alpha = 0.1 * abs(math.log(99 / 100)) / (sigma * math.sqrt(2))
    expected = 110 + alpha * (99 - 110)
    assert adaptive_ma(series, 2).iloc[2] == pytest.approx(expected, rel=1e-12)


def test_adaptive_ma_flat_window_resets_to_close():
    # A perfectly flat window has zero volatility -> undefined (0/0) -> NaN, and the
    # running value resets to that bar's close, same as the charting library.
    series = pd.Series([100.0] * 5 + [120.0, 130.0])
    result = adaptive_ma(series, 3)
    assert result.iloc[3:5].isna().all()
    assert result.iloc[5:].notna().all()


def test_adaptive_ma_short_series_all_nan():
    assert adaptive_ma(pd.Series([1.0, 2.0, 3.0]), 5).isna().all()


def test_adaptive_ma_matches_nepsealpha_chart_for_hdl():
    """Golden values read off NepseAlpha's 1D HDL chart for the 2026-11-26 candle.

    20 and 50 match to the paisa. 150 and 200 drift slightly because NepseAlpha
    back-adjusts prices for HDL's 20% bonus (pre-2025-11-06 closes / 1.2) while our
    sharesansar history is unadjusted; on NepseAlpha's own adjusted closes, all four
    periods match exactly.
    """
    csv_path = Path(__file__).resolve().parents[1] / "data" / "history" / "HDL.csv"
    df = pd.read_csv(csv_path)
    close = df.loc[df["date"] <= "2026-11-26", "close"].reset_index(drop=True)
    assert len(close) == 394  # guards against the fixture history being rewritten

    assert adaptive_ma(close, 20).iloc[-1] == pytest.approx(1319.78, abs=0.02)
    assert adaptive_ma(close, 50).iloc[-1] == pytest.approx(1328.98, abs=0.02)
    assert adaptive_ma(close, 150).iloc[-1] == pytest.approx(1320.02, rel=0.005)
    assert adaptive_ma(close, 200).iloc[-1] == pytest.approx(1314.20, rel=0.005)
