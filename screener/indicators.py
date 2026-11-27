import numpy as np
import pandas as pd

# NEPSE trades Monday-Friday (Sunday-Thursday before July 2026), with frequent public
# holidays. Every window here is a count of trading sessions, not calendar days, so the
# change of trading week needs no recalibration. "52 weeks" is a trading-session
# approximation (235) rather than 252, since holidays cut NEPSE's sessions per year.
WEEK52_SESSIONS = 235
TREND_LOOKBACK_SESSIONS = 20

AMA_ALPHA_SCALE = 0.1


def adaptive_ma(close: pd.Series, period: int) -> pd.Series:
    """"Moving Average Adaptive", exactly as NepseAlpha's chart computes it.

    This is a port of TradingView Charting Library's built-in study
    `Moving Average Adaptive@tv-basicstudies-1` (single input: "Period"), which is what
    nepsealpha.com's chart runs. It is NOT Kaufman's AMA (KAMA): the speed comes from
    trend strength measured against volatility, not from an efficiency ratio.

        r      = ln(close / close[1])                       per-bar log return
        sigma  = stdev(r, period)                           population stdev (ddof=0)
        signal = ln(close / close[period]) / (sigma * sqrt(period))
        alpha  = 0.1 * |signal|
        ama    = ama[1] + alpha * (close - ama[1])

    Bars where any of that is undefined (the first `period` bars, or a flat window where
    sigma == 0) output NaN, and the running value is reset to that bar's close, the same
    as the library's `isNaN(c) ? close : c`. Verified against NepseAlpha's 1D chart for
    HDL on 2026-11-26 (periods 20/50/150/200 match to 0.01).
    """
    c = close.to_numpy(dtype=float)
    n = len(c)
    out = np.full(n, np.nan)
    if n <= period:
        return pd.Series(out, index=close.index)

    log_ret = np.full(n, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_ret[1:] = np.log(c[1:] / c[:-1])
        sigma = pd.Series(log_ret).rolling(period, min_periods=period).std(ddof=0).to_numpy()
        momentum = np.full(n, np.nan)
        momentum[period:] = np.log(c[period:] / c[:-period])
        alpha = AMA_ALPHA_SCALE * np.abs(momentum / (sigma * np.sqrt(period)))

    prev = np.nan
    for i in range(n):
        value = prev + alpha[i] * (c[i] - prev)
        if np.isfinite(value):
            out[i] = value
            prev = value
        else:
            prev = c[i]

    return pd.Series(out, index=close.index)


def is_trending_up(ma_series: pd.Series, lookback: int = TREND_LOOKBACK_SESSIONS):
    """True/False if there's enough history to compare, else None (unknown)."""
    valid = ma_series.dropna()
    if len(valid) < lookback + 1:
        return None
    latest = valid.iloc[-1]
    past = valid.iloc[-1 - lookback]
    return bool(latest > past)


def week52_high_low(close: pd.Series, sessions: int = WEEK52_SESSIONS):
    window = close.tail(sessions)
    return float(window.max()), float(window.min())
