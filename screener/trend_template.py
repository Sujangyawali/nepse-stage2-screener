import pandas as pd

from screener.indicators import is_trending_up, sma, week52_high_low

MIN_HISTORY_SESSIONS = 200

# Single-session % move beyond which we suspect an unadjusted bonus/rights-share ex-date
# gap rather than a normal trade — NEPSE's circuit-breaker bands bound ordinary daily moves
# well under this. This is a heuristic warning flag only; prices are NOT auto-corrected.
CORPORATE_ACTION_GAP_THRESHOLD = 0.18

# The 8 Minervini Trend Template criteria. "rs_top_30pct" is left False here and filled in
# by build_output.py once universe.py has computed the cross-sectional RS percentile —
# it can't be known from a single symbol's history alone.
CRITERIA_KEYS = [
    "price_above_150_200",
    "sma150_above_sma200",
    "sma200_trending_up",
    "sma50_above_150_200",
    "price_above_sma50",
    "above_52w_low_25pct",
    "within_25pct_52w_high",
    "rs_top_30pct",
]


def _empty_result(df: pd.DataFrame) -> dict:
    latest_close = float(df["close"].iloc[-1]) if len(df) else None
    return {
        "close": latest_close,
        "sma50": None,
        "sma150": None,
        "sma200": None,
        "week52_high": None,
        "week52_low": None,
        "pct_above_52w_low": None,
        "pct_from_52w_high": None,
        "history_days_available": len(df),
        "data_quality": {
            "sufficient_history": False,
            "possible_corporate_action_gap": _has_corporate_action_gap(df["close"]) if len(df) else False,
        },
        "criteria": {k: False for k in CRITERIA_KEYS},
    }


def _has_corporate_action_gap(close: pd.Series) -> bool:
    if len(close) < 2:
        return False
    pct_change = close.pct_change().abs()
    return bool((pct_change > CORPORATE_ACTION_GAP_THRESHOLD).any())


def evaluate(df: pd.DataFrame) -> dict:
    """
    df must have a 'close' column sorted ascending by date (oldest first).
    Returns the per-symbol trend-template fields; 'criteria.rs_top_30pct' and the
    overall 'score'/'is_candidate' are filled in later by build_output.py.
    """
    df = df.reset_index(drop=True)
    if len(df) < MIN_HISTORY_SESSIONS:
        return _empty_result(df)

    close = df["close"]
    sma50 = sma(close, 50)
    sma150 = sma(close, 150)
    sma200 = sma(close, 200)

    latest_close = float(close.iloc[-1])
    latest_sma50 = float(sma50.iloc[-1])
    latest_sma150 = float(sma150.iloc[-1])
    latest_sma200 = float(sma200.iloc[-1])

    week52_high, week52_low = week52_high_low(close)
    trending_up = is_trending_up(sma200)

    pct_above_52w_low = (latest_close / week52_low - 1) * 100 if week52_low else None
    pct_from_52w_high = (1 - latest_close / week52_high) * 100 if week52_high else None

    criteria = {
        "price_above_150_200": latest_close > latest_sma150 and latest_close > latest_sma200,
        "sma150_above_sma200": latest_sma150 > latest_sma200,
        "sma200_trending_up": bool(trending_up),
        "sma50_above_150_200": latest_sma50 > latest_sma150 and latest_sma50 > latest_sma200,
        "price_above_sma50": latest_close > latest_sma50,
        "above_52w_low_25pct": pct_above_52w_low is not None and pct_above_52w_low >= 25,
        "within_25pct_52w_high": pct_from_52w_high is not None and pct_from_52w_high <= 25,
        "rs_top_30pct": False,
    }
    criteria = {k: bool(v) for k, v in criteria.items()}

    return {
        "close": latest_close,
        "sma50": latest_sma50,
        "sma150": latest_sma150,
        "sma200": latest_sma200,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "pct_above_52w_low": pct_above_52w_low,
        "pct_from_52w_high": pct_from_52w_high,
        "history_days_available": len(df),
        "data_quality": {
            "sufficient_history": True,
            "possible_corporate_action_gap": _has_corporate_action_gap(close),
        },
        "criteria": criteria,
    }
