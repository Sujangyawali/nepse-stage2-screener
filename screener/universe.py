import pandas as pd

# Trailing-return windows approximating 3/6/9/12 months at NEPSE's ~4-5 day trading week
# (IBD/Minervini-style blended relative strength). Weighted toward the most recent window,
# consistent with the standard RS-rating formula.
RS_WINDOWS = [65, 130, 195, 260]
RS_WEIGHTS = [0.4, 0.2, 0.2, 0.2]


def _trailing_return(close: pd.Series, window: int):
    if len(close) <= window:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - window] - 1)


def compute_rs_score(close: pd.Series):
    """Weighted blend of trailing returns; None if there isn't enough history for any window."""
    scores = []
    weights = []
    for window, weight in zip(RS_WINDOWS, RS_WEIGHTS):
        ret = _trailing_return(close, window)
        if ret is not None:
            scores.append(ret)
            weights.append(weight)
    if not scores:
        return None
    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)


def rank_universe(rs_scores: dict) -> dict:
    """
    rs_scores: {symbol: rs_score or None}. Returns {symbol: percentile 0-100}, ranked only
    among symbols with a real score — symbols with None are excluded from ranking (and the
    caller should treat their rs_top_30pct criterion as failing, not passing by default).
    """
    valid = {sym: score for sym, score in rs_scores.items() if score is not None}
    if not valid:
        return {sym: None for sym in rs_scores}

    ranked_symbols = sorted(valid, key=lambda s: valid[s])
    n = len(ranked_symbols)
    percentiles = {}
    for i, sym in enumerate(ranked_symbols):
        # rank i=0 is the worst performer -> percentile ~0; i=n-1 is best -> percentile ~100
        percentiles[sym] = round((i / (n - 1)) * 100, 1) if n > 1 else 100.0

    return {sym: percentiles.get(sym) for sym in rs_scores}
