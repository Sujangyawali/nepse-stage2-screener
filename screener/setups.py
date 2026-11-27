"""Minervini-style setup detection: Volatility Contraction Patterns (VCP) and breakouts.

The Trend Template (screener.trend_template) says a stock is in a Stage 2 uptrend; this
module looks for *when* to buy one. Minervini's preferred entry is a VCP: a base in which
each pullback ("contraction", T1, T2, ...) is shallower than the previous one while volume
dries up, so supply is exhausted just below a pivot. The buy signal is a close through the
pivot on a volume surge.

Thresholds below are rules of thumb from Minervini's books and common quantifications of
them (e.g. first contraction up to ~35-40%, final contraction tight, breakout volume ~40-50%
above average); they are deliberately exposed as module constants so they're easy to tune.
"""
import math

import pandas as pd

BASE_LOOKBACK_SESSIONS = 130   # ~6 months: where we look for the base's left-side peak
MIN_BASE_SESSIONS = 15         # Minervini: a base needs at least ~3 weeks
# A reversal of SWING_VOL_MULTIPLE x the stock's median daily move (clamped to 4-10%)
# confirms a swing; a fixed small threshold would count ordinary daily noise as contractions.
SWING_VOL_MULTIPLE = 2.5
SWING_MIN, SWING_MAX = 0.04, 0.10
MAX_CONTRACTIONS = 6           # more than this is a loose, choppy base rather than a VCP
MAX_FIRST_CONTRACTION = 0.40   # deeper than this is a broken base, not a VCP
MAX_LAST_CONTRACTION = 0.15    # the final contraction must be tight
CONTRACTION_TOLERANCE = 0.01   # allow +1 percentage point of noise between contractions
READY_WITHIN_PCT = 5.0         # "ready" = close within 5% below the pivot
DRY_UP_RATIO = 0.8             # 10-day avg volume <= 80% of 50-day avg = volume drying up
BREAKOUT_VOLUME_RATIO = 1.5    # breakout day volume >= 1.5x the 50-day average
TIGHT_DAYS = 10
# A new-52-week-high breakout only counts as an entry when the previous high is at least
# this old, i.e. the stock is leaving a consolidation, not just extending a run.
MIN_SESSIONS_SINCE_PRIOR_HIGH = 10
MAX_STOP_PCT = 8.0             # Minervini: never risk more than ~7-8% below the buy point

STATUS_ORDER = ["breakout", "breakout_low_volume", "ready", "forming"]


def _swing_threshold(close) -> float:
    rets = pd.Series(close).pct_change().abs().tail(60).dropna()
    typical = float(rets.median()) if len(rets) else 0.0
    return min(max(SWING_VOL_MULTIPLE * typical, SWING_MIN), SWING_MAX)


def _swings(high, low, start: int, threshold: float) -> list:
    """Zig-zag swing points from `start` (the base's peak) to the end of the series.

    Returns [(index, price, "H" | "L"), ...] starting with the peak. The final point is
    provisional (the current, not-yet-reversed extreme)."""
    points = [(start, high[start], "H")]
    seeking = "L"
    cand_i, cand_p = start, low[start]
    for i in range(start + 1, len(high)):
        if seeking == "L":
            if high[i] > points[-1][1]:
                # New high before any pullback was confirmed: the swing high moves up.
                points[-1] = (i, high[i], "H")
                cand_i, cand_p = i, low[i]
                continue
            if low[i] < cand_p:
                cand_i, cand_p = i, low[i]
            if high[i] >= cand_p * (1 + threshold):
                points.append((cand_i, cand_p, "L"))
                seeking = "H"
                cand_i, cand_p = i, high[i]
        else:
            if high[i] > cand_p:
                cand_i, cand_p = i, high[i]
            if low[i] <= cand_p * (1 - threshold):
                points.append((cand_i, cand_p, "H"))
                seeking = "L"
                cand_i, cand_p = i, low[i]
    points.append((cand_i, cand_p, "H" if seeking == "H" else "L"))
    return points


def analyze_base(df: pd.DataFrame) -> dict | None:
    """Describe the base the stock is currently in, or None if there isn't one.

    `df` needs high/low/close/volume columns, oldest first."""
    if len(df) < max(MIN_BASE_SESSIONS + 5, 60):
        return None
    window = df.tail(BASE_LOOKBACK_SESSIONS).reset_index(drop=True)
    high = window["high"].fillna(window["close"]).to_numpy(dtype=float)
    low = window["low"].fillna(window["close"]).to_numpy(dtype=float)
    close = window["close"].to_numpy(dtype=float)
    n = len(window)

    peak = int(high.argmax())
    base_length = n - 1 - peak
    if base_length < MIN_BASE_SESSIONS:
        return None  # at/near highs: no base yet (breakouts are detected separately)

    points = _swings(high, low, peak, _swing_threshold(close))
    contractions = []
    for k in range(len(points) - 1):
        (hi_i, hi_p, hi_t), (lo_i, lo_p, lo_t) = points[k], points[k + 1]
        if hi_t == "H" and lo_t == "L":
            contractions.append({"high": hi_p, "low": lo_p, "depth": (hi_p - lo_p) / hi_p,
                                 "high_index": hi_i, "low_index": lo_i})
    if not contractions:
        return None

    # The pattern is judged from the deepest pullback (T1) onward; earlier, shallower
    # wiggles near the peak are part of the topping/handle action, not the contraction set.
    deepest = max(range(len(contractions)), key=lambda k: contractions[k]["depth"])
    contractions = contractions[deepest:]
    depths = [c["depth"] for c in contractions]
    last = contractions[-1]
    # Pivot: the high of the last contraction. If price has since rallied above it without
    # a confirmed new swing, the base's most recent swing high is still the reference.
    pivot = last["high"]
    contracting = all(depths[k] <= depths[k - 1] + CONTRACTION_TOLERANCE for k in range(1, len(depths)))
    is_vcp = (
        2 <= len(contractions) <= MAX_CONTRACTIONS
        and contracting
        and depths[0] <= MAX_FIRST_CONTRACTION
        and depths[-1] <= MAX_LAST_CONTRACTION
    )

    vol = window["volume"].to_numpy(dtype=float)
    vol50 = _mean(vol[-50:])
    vol10 = _mean(vol[-TIGHT_DAYS:])
    recent_high = high[-TIGHT_DAYS:].max()
    recent_low = low[-TIGHT_DAYS:].min()

    return {
        "base_peak": float(high[peak]),
        "base_length": int(base_length),
        "base_depth_pct": round(float((high[peak] - low[peak:].min()) / high[peak]) * 100, 1),
        "contractions_pct": [round(float(d) * 100, 1) for d in depths],
        "t_count": len(contractions),
        "is_vcp": bool(is_vcp),
        "pivot": round(float(pivot), 2),
        "last_low": round(float(last["low"]), 2),
        "close": float(close[-1]),
        "dist_to_pivot_pct": round((pivot / close[-1] - 1) * 100, 2),
        "tightness_pct": round((recent_high - recent_low) / close[-1] * 100, 1),
        "volume_dry_up_ratio": round(vol10 / vol50, 2) if vol50 else None,
    }


def _mean(values) -> float:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    return sum(clean) / len(clean) if clean else 0.0


def evaluate_setup(df: pd.DataFrame) -> dict | None:
    """Setup status for one stock as of its last session, or None if nothing qualifies.

    Breakouts are judged against the base as it stood *before* today, so today's bar can't
    move its own pivot."""
    df = df.reset_index(drop=True)
    if len(df) < 61:
        return None
    today = df.iloc[-1]
    prior = df.iloc[:-1]
    vol = df["volume"].to_numpy(dtype=float)
    avg50 = _mean(vol[-51:-1])
    breakout_volume_ratio = round(vol[-1] / avg50, 2) if avg50 else None
    volume_ok = breakout_volume_ratio is not None and breakout_volume_ratio >= BREAKOUT_VOLUME_RATIO

    base_before = analyze_base(prior)
    base_now = analyze_base(df)
    close = float(today["close"])
    prev_close = float(prior["close"].iloc[-1])

    breakout_type = None
    pivot_used = None
    if base_before and base_before["is_vcp"] and close > base_before["pivot"] >= prev_close:
        breakout_type, pivot_used = "vcp_pivot", base_before["pivot"]
    else:
        prior_highs = prior["high"].fillna(prior["close"]).tail(235).reset_index(drop=True)
        prior_52w_high = float(prior_highs.max())
        sessions_since_high = len(prior_highs) - 1 - int(prior_highs.idxmax())
        if close > prior_52w_high >= prev_close and sessions_since_high >= MIN_SESSIONS_SINCE_PRIOR_HIGH:
            breakout_type, pivot_used = "52w_high", prior_52w_high

    if breakout_type:
        base = base_before or base_now or {}
        status = "breakout" if volume_ok else "breakout_low_volume"
        pivot = pivot_used
    elif base_now and base_now["is_vcp"] and base_now["dist_to_pivot_pct"] >= 0:
        base = base_now
        status = "ready" if base_now["dist_to_pivot_pct"] <= READY_WITHIN_PCT else "forming"
        pivot = base_now["pivot"]
    else:
        return None

    # Suggested stop: under the last contraction's low, but never more than MAX_STOP_PCT
    # below the pivot (Minervini's ~7-8% maximum loss rule).
    stop_floor = pivot * (1 - MAX_STOP_PCT / 100)
    last_low = base.get("last_low")
    stop = max(last_low, stop_floor) if last_low and last_low < pivot else stop_floor

    return {
        "status": status,
        "breakout_type": breakout_type,
        "pivot": round(float(pivot), 2),
        "dist_to_pivot_pct": round((pivot / close - 1) * 100, 2),
        "stop": round(float(stop), 2),
        "risk_pct": round((pivot - stop) / pivot * 100, 1),
        "breakout_volume_ratio": breakout_volume_ratio,
        "base_length": base.get("base_length"),
        "base_depth_pct": base.get("base_depth_pct"),
        "contractions_pct": base.get("contractions_pct", []),
        "t_count": base.get("t_count"),
        "is_vcp": base.get("is_vcp", False),
        "tightness_pct": base.get("tightness_pct"),
        "volume_dry_up_ratio": base.get("volume_dry_up_ratio"),
    }
