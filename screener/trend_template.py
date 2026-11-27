import pandas as pd

from screener.indicators import adaptive_ma, is_trending_up, week52_high_low

# adaptive_ma(period=200) needs period + 1 closes before it produces its first value.
MIN_HISTORY_SESSIONS = 201

# Periods shown alongside price (matching the four "Moving Average Adaptive" lines on
# NepseAlpha). The Trend Template itself only uses 50/150/200; 20 is informational.
MA_PERIODS = (20, 50, 150, 200)

# Liquidity: Minervini avoids thinly traded stocks (hard to enter/exit without moving the
# price). Average daily turnover is approximated as close x volume over the last 50
# sessions, since actual turnover is only stored from 2026-11-27 onward. A stock below the
# minimum can still score 8/8 but is not a candidate or setup.
LIQUIDITY_SESSIONS = 50
MIN_AVG_DAILY_TURNOVER = 5_000_000  # Rs 50 lakh

# Single-session % move beyond which we suspect an unadjusted bonus/rights-share ex-date
# gap rather than a normal trade — NEPSE's circuit-breaker bands bound ordinary daily moves
# well under this. This is a heuristic warning flag only; prices are NOT auto-corrected.
CORPORATE_ACTION_GAP_THRESHOLD = 0.18

# Minervini-style Trend Template (8 criteria), evaluated against NepseAlpha-compatible
# adaptive moving averages (see screener.indicators.adaptive_ma) instead of SMAs.
#
# Minervini's two MA-*ordering* rules (150 above 200; 50 above 150 & 200) are replaced
# with price-vs-MA rules. With this indicator a LONGER period reacts FASTER (its speed is
# ln(close/close[P]) / (stdev * sqrt(P)), which grows with sqrt(P) in a steady trend), so
# in a clean uptrend the stack is price > AMA200 > AMA150 > AMA50 — the reverse of SMAs —
# and the original ordering rules would reject exactly the strongest trends.
# "rs_top_30pct" is left False here and filled in by build_output.py once universe.py has
# computed the cross-sectional RS percentile — it can't be known from a single symbol's
# history alone.
CRITERIA_KEYS = [
    "price_above_150_200",
    "price_above_ma20",
    "ma200_trending_up",
    "price_above_all_ma",
    "price_above_ma50",
    "above_52w_low_25pct",
    "within_25pct_52w_high",
    "rs_top_30pct",
]


def _empty_result(df: pd.DataFrame) -> dict:
    latest_close = float(df["close"].iloc[-1]) if len(df) else None
    return {
        "close": latest_close,
        "ma20": None,
        "ma50": None,
        "ma150": None,
        "ma200": None,
        "week52_high": None,
        "week52_low": None,
        "pct_above_52w_low": None,
        "pct_from_52w_high": None,
        "history_days_available": len(df),
        "avg_daily_turnover": _avg_daily_turnover(df),
        "data_quality": {
            "sufficient_history": False,
            "liquid": _is_liquid(_avg_daily_turnover(df)),
            "possible_corporate_action_gap": _has_corporate_action_gap(df["close"]) if len(df) else False,
        },
        "criteria": {k: False for k in CRITERIA_KEYS},
    }


def _avg_daily_turnover(df: pd.DataFrame):
    if "volume" not in df.columns or not len(df):
        return None
    recent = df.tail(LIQUIDITY_SESSIONS)
    value = (recent["close"] * recent["volume"]).mean()
    return None if pd.isna(value) else float(value)


def _is_liquid(avg_turnover) -> bool:
    # Unknown (no volume data) is not penalised; only a measured shortfall is.
    return avg_turnover is None or avg_turnover >= MIN_AVG_DAILY_TURNOVER


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
    ma = {period: adaptive_ma(close, period) for period in MA_PERIODS}
    ma50, ma150, ma200 = ma[50], ma[150], ma[200]

    latest_close = float(close.iloc[-1])
    latest_ma20 = float(ma[20].iloc[-1])
    latest_ma50 = float(ma50.iloc[-1])
    latest_ma150 = float(ma150.iloc[-1])
    latest_ma200 = float(ma200.iloc[-1])

    week52_high, week52_low = week52_high_low(close)
    avg_turnover = _avg_daily_turnover(df)
    trending_up = is_trending_up(ma200)

    pct_above_52w_low = (latest_close / week52_low - 1) * 100 if week52_low else None
    pct_from_52w_high = (1 - latest_close / week52_high) * 100 if week52_high else None

    criteria = {
        "price_above_150_200": latest_close > latest_ma150 and latest_close > latest_ma200,
        "price_above_ma20": latest_close > latest_ma20,
        "ma200_trending_up": bool(trending_up),
        "price_above_all_ma": all(
            latest_close > m for m in (latest_ma20, latest_ma50, latest_ma150, latest_ma200)
        ),
        "price_above_ma50": latest_close > latest_ma50,
        "above_52w_low_25pct": pct_above_52w_low is not None and pct_above_52w_low >= 25,
        "within_25pct_52w_high": pct_from_52w_high is not None and pct_from_52w_high <= 25,
        "rs_top_30pct": False,
    }
    criteria = {k: bool(v) for k, v in criteria.items()}

    return {
        "close": latest_close,
        "ma20": latest_ma20,
        "ma50": latest_ma50,
        "ma150": latest_ma150,
        "ma200": latest_ma200,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "pct_above_52w_low": pct_above_52w_low,
        "pct_from_52w_high": pct_from_52w_high,
        "history_days_available": len(df),
        "avg_daily_turnover": avg_turnover,
        "data_quality": {
            "sufficient_history": True,
            "liquid": _is_liquid(avg_turnover),
            "possible_corporate_action_gap": _has_corporate_action_gap(close),
        },
        "criteria": criteria,
    }
