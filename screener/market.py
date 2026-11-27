"""Market direction from an equal-weight index of the screened universe.

Minervini (following O'Neil) only buys breakouts when the general market is healthy. There
is no scrapeable NEPSE index history, so we build an equal-weight index from our own
equities: each session's index return is the average log return of every stock that
traded. Single-day moves beyond CORPORATE_ACTION_GAP (unadjusted bonus/rights ex-dates)
are excluded so they don't masquerade as market crashes.

Status, judged on the index vs. its 50-session simple average:
  Uptrend    — index above the average AND the average rising
  Correction — index below the average AND the average falling
  Caution    — mixed signals (e.g. a rally attempt inside a downtrend)
A simple average is used here deliberately: the NepseAlpha-style adaptive MA reacts too
fast to serve as a market regime filter.
"""
import numpy as np
import pandas as pd

INDEX_BASE = 1000.0
MA_SESSIONS = 50
SLOPE_SESSIONS = 10
MIN_STOCKS_PER_SESSION = 100
CORPORATE_ACTION_GAP = 0.18
HISTORY_SESSIONS = 130
WEEK52_SESSIONS = 235


def equal_weight_index(histories: dict) -> pd.DataFrame:
    returns = {}
    for sym, df in histories.items():
        if df.empty:
            continue
        close = df.set_index("date")["close"]
        r = np.log(close / close.shift(1))
        returns[sym] = r.where(r.abs() < CORPORATE_ACTION_GAP)
    if not returns:
        return pd.DataFrame(columns=["index", "ma50"])
    frame = pd.DataFrame(returns).sort_index()
    counts = frame.notna().sum(axis=1)
    # Skip the early sessions where too few stocks have history to be representative.
    daily = frame.mean(axis=1)[counts >= MIN_STOCKS_PER_SESSION].fillna(0.0)
    index = INDEX_BASE * np.exp(daily.cumsum())
    return pd.DataFrame({"index": index, "ma50": index.rolling(MA_SESSIONS).mean()})


def _new_highs_lows(histories: dict, as_of) -> tuple:
    highs = lows = 0
    for df in histories.values():
        if len(df) < 2 or df["date"].iloc[-1] != as_of:
            continue
        close = df["close"]
        prior = close.iloc[-1 - WEEK52_SESSIONS:-1]
        if close.iloc[-1] > prior.max():
            highs += 1
        elif close.iloc[-1] < prior.min():
            lows += 1
    return highs, lows


def market_direction(histories: dict) -> dict | None:
    idx = equal_weight_index(histories).dropna()
    if len(idx) <= SLOPE_SESSIONS:
        return None
    last, ma = float(idx["index"].iloc[-1]), float(idx["ma50"].iloc[-1])
    ma_before = float(idx["ma50"].iloc[-1 - SLOPE_SESSIONS])
    rising = ma > ma_before
    if last > ma and rising:
        status = "uptrend"
    elif last < ma and not rising:
        status = "correction"
    else:
        status = "caution"

    as_of = idx.index[-1]
    new_highs, new_lows = _new_highs_lows(histories, as_of)
    tail = idx.tail(HISTORY_SESSIONS)
    return {
        "status": status,
        "as_of_trading_date": as_of.strftime("%Y-%m-%d"),
        "index": round(last, 2),
        "ma50": round(ma, 2),
        "pct_vs_ma50": round((last / ma - 1) * 100, 2),
        "ma50_rising": bool(rising),
        "ma50_change_pct": round((ma / ma_before - 1) * 100, 2),
        "new_52w_highs": new_highs,
        "new_52w_lows": new_lows,
        "history": [
            {"date": d.strftime("%Y-%m-%d"), "index": round(float(r["index"]), 2), "ma50": round(float(r["ma50"]), 2)}
            for d, r in tail.iterrows()
        ],
    }
