import numpy as np
import pandas as pd

# NEPSE trades ~4-5 days/week (Sun-Thu) rather than the 5-day week Minervini's original
# 50/150/200 *day* windows assume. We treat these as trading-session counts, which
# naturally handles the shorter week without recalibration. "52 weeks" similarly becomes
# a trading-session approximation rather than 252 (the standard 5-day-week figure).
WEEK52_SESSIONS = 235
TREND_LOOKBACK_SESSIONS = 20

KAMA_ER_PERIOD = 10
KAMA_FAST_PERIOD = 2


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def kama(series: pd.Series, er_period: int = KAMA_ER_PERIOD, fast_period: int = KAMA_FAST_PERIOD,
         slow_period: int = 30) -> pd.Series:
    """Kaufman's Adaptive Moving Average.

    Unlike a fixed-window SMA, KAMA speeds up (tracks price closely) when the market is
    moving efficiently in one direction and slows down (behaves like a heavily-smoothed
    average) when it's choppy/sideways — measured by the efficiency ratio (net change over
    `er_period` bars, divided by the sum of bar-to-bar moves over the same window).
    `slow_period` plays the same role an SMA window plays during low-efficiency stretches,
    which is why callers reuse 50/150/200 as `slow_period` to build an AMA50/150/200 trio
    comparable to the SMA-based Trend Template.
    """
    values = series.to_numpy(dtype=float)
    n = len(values)
    result = np.full(n, np.nan)
    if n <= er_period:
        return pd.Series(result, index=series.index)

    change = np.abs(values[er_period:] - values[:-er_period])
    abs_diffs = pd.Series(values).diff().abs()
    volatility = abs_diffs.rolling(er_period).sum().to_numpy()[er_period:]
    with np.errstate(divide="ignore", invalid="ignore"):
        efficiency_ratio = np.where(volatility == 0, 0.0, change / volatility)

    fast_sc = 2 / (fast_period + 1)
    slow_sc = 2 / (slow_period + 1)
    smoothing_constant = (efficiency_ratio * (fast_sc - slow_sc) + slow_sc) ** 2

    result[er_period] = values[er_period]
    for i in range(er_period + 1, n):
        sc = smoothing_constant[i - er_period]
        result[i] = result[i - 1] + sc * (values[i] - result[i - 1])

    return pd.Series(result, index=series.index)


def moving_average(close: pd.Series, window: int, method: str = "sma") -> pd.Series:
    """Dispatch to the right moving-average implementation for a Trend Template variant."""
    if method == "sma":
        return sma(close, window)
    if method == "ama":
        return kama(close, slow_period=window)
    raise ValueError(f"unknown moving-average method {method!r}")


def is_trending_up(sma_series: pd.Series, lookback: int = TREND_LOOKBACK_SESSIONS):
    """True/False if there's enough history to compare, else None (unknown)."""
    valid = sma_series.dropna()
    if len(valid) < lookback + 1:
        return None
    latest = valid.iloc[-1]
    past = valid.iloc[-1 - lookback]
    return bool(latest > past)


def week52_high_low(close: pd.Series, sessions: int = WEEK52_SESSIONS):
    window = close.tail(sessions)
    return float(window.max()), float(window.min())
