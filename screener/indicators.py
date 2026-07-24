import pandas as pd

# NEPSE trades ~4-5 days/week (Sun-Thu) rather than the 5-day week Minervini's original
# 50/150/200 *day* windows assume. We treat these as trading-session counts, which
# naturally handles the shorter week without recalibration. "52 weeks" similarly becomes
# a trading-session approximation rather than 252 (the standard 5-day-week figure).
WEEK52_SESSIONS = 235
TREND_LOOKBACK_SESSIONS = 20


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


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
