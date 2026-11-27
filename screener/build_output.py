import json
from datetime import datetime

from scraper.config import DOCS_DATA_DIR, TIMEZONE
from scraper.sector_filter import load_symbols_meta
from scraper.storage import known_symbols, load_history
from screener.indicators import adaptive_ma
from screener.trend_template import MA_PERIODS, evaluate
from screener.universe import compute_rs_score, rank_universe

RS_TOP_PERCENTILE_THRESHOLD = 70  # "top 30%" of the universe
CANDIDATE_SCORE_THRESHOLD = 8  # all 8 criteria must pass by default

HISTORY_CHART_SESSIONS = 300


def _equity_symbols_with_history() -> list:
    meta = load_symbols_meta()
    symbols = known_symbols()
    return [s for s in symbols if meta.get(s, {}).get("is_equity", False)]


def _evaluate_universe(symbols: list, histories: dict, meta: dict, rs_percentiles: dict) -> tuple:
    """Evaluate every symbol against the Trend Template (adaptive-MA based)."""
    stocks = []
    as_of_dates = []
    for sym in symbols:
        df = histories[sym]
        result = evaluate(df)
        percentile = rs_percentiles.get(sym)
        result["criteria"]["rs_top_30pct"] = bool(
            percentile is not None and percentile >= RS_TOP_PERCENTILE_THRESHOLD
        )
        score = sum(1 for v in result["criteria"].values() if v)
        is_candidate = (
            result["data_quality"]["sufficient_history"]
            and score >= CANDIDATE_SCORE_THRESHOLD
        )

        if len(df):
            as_of_dates.append(df["date"].iloc[-1])

        stocks.append({
            "symbol": sym,
            "name": meta.get(sym, {}).get("name", ""),
            "sector": meta.get(sym, {}).get("sector", ""),
            "close": result["close"],
            "ma20": result["ma20"],
            "ma50": result["ma50"],
            "ma150": result["ma150"],
            "ma200": result["ma200"],
            "week52_high": result["week52_high"],
            "week52_low": result["week52_low"],
            "pct_above_52w_low": result["pct_above_52w_low"],
            "pct_from_52w_high": result["pct_from_52w_high"],
            "rs_percentile": percentile,
            "criteria": result["criteria"],
            "score": score,
            "is_candidate": is_candidate,
            "history_days_available": result["history_days_available"],
            "data_quality": result["data_quality"],
        })

    stocks.sort(key=lambda s: (s["score"], s["rs_percentile"] or 0), reverse=True)
    candidates_count = sum(1 for s in stocks if s["is_candidate"])

    return {
        "universe_size": len(stocks),
        "candidates_count": candidates_count,
        "stocks": stocks,
    }, as_of_dates


def build_candidates() -> dict:
    meta = load_symbols_meta()
    symbols = _equity_symbols_with_history()
    histories = {sym: load_history(sym) for sym in symbols}

    # Relative strength is based on raw price returns (not moving averages) and is ranked
    # across the whole universe, so it has to be computed before per-symbol scoring.
    rs_scores = {
        sym: compute_rs_score(histories[sym]["close"]) if len(histories[sym]) else None
        for sym in symbols
    }
    rs_percentiles = rank_universe(rs_scores)

    block, as_of_dates = _evaluate_universe(symbols, histories, meta, rs_percentiles)
    as_of_trading_date = max(as_of_dates).strftime("%Y-%m-%d") if as_of_dates else None

    return {
        "generated_at": datetime.now(TIMEZONE).isoformat(),
        "as_of_trading_date": as_of_trading_date,
        **block,
    }, histories


def write_history_json(symbol: str, df) -> dict:
    # Compute moving averages on the full history first so the trailing display window's
    # early points still get a full lookback (e.g. a 200-window MA needs 200 prior rows) —
    # trimming before computing would starve the first ~200 chart points of their value.
    # The adaptive MA is also recursive, so its value depends on all earlier bars.
    full_close = df["close"]
    ma_full = {period: adaptive_ma(full_close, period) for period in MA_PERIODS}

    df = df.tail(HISTORY_CHART_SESSIONS).reset_index(drop=True)
    tail_index = full_close.tail(HISTORY_CHART_SESSIONS).index
    close = df["close"]
    ma_tail = {key: series.loc[tail_index].reset_index(drop=True) for key, series in ma_full.items()}

    series = []
    for i, row in enumerate(df.itertuples()):
        entry = {
            "date": row.date.strftime("%Y-%m-%d") if hasattr(row.date, "strftime") else str(row.date),
            "close": None if pd_isna(close[i]) else float(close[i]),
        }
        for period in MA_PERIODS:
            value = ma_tail[period][i]
            entry[f"ama{period}"] = None if pd_isna(value) else float(value)
        series.append(entry)

    return {"symbol": symbol, "series": series}


def pd_isna(value) -> bool:
    return value != value  # NaN != NaN


def _json_safe(value):
    """Recursively replace NaN with None — Python's json.dumps emits bare `NaN`, which is
    not valid JSON and makes the frontend's JSON.parse() throw on the whole payload."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and value != value:
        return None
    return value


def run(write_history_for_all: bool = False) -> dict:
    candidates, histories = build_candidates()

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    history_dir = DOCS_DATA_DIR / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    (DOCS_DATA_DIR / "candidates.json").write_text(json.dumps(_json_safe(candidates), indent=2))

    meta = {
        "generated_at": candidates["generated_at"],
        "as_of_trading_date": candidates["as_of_trading_date"],
        "universe_size": candidates["universe_size"],
        "candidates_count": candidates["candidates_count"],
    }
    (DOCS_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))

    if write_history_for_all:
        symbols_to_chart = set(histories.keys())
    else:
        symbols_to_chart = {s["symbol"] for s in candidates["stocks"] if s["is_candidate"]}
        # Drop charts for symbols that are no longer candidates, so the site never serves
        # a stale history file computed by an older run (or an older MA formula).
        for stale in history_dir.glob("*.json"):
            if stale.stem not in symbols_to_chart:
                stale.unlink()

    for symbol in symbols_to_chart:
        df = histories.get(symbol)
        if df is None or df.empty:
            continue
        chart_data = write_history_json(symbol, df)
        (history_dir / f"{symbol}.json").write_text(json.dumps(_json_safe(chart_data), indent=2))

    return candidates


if __name__ == "__main__":
    import sys

    result = run(write_history_for_all="--all-history" in sys.argv)
    print(
        f"universe_size={result['universe_size']} "
        f"candidates={result['candidates_count']} "
        f"as_of={result['as_of_trading_date']}"
    )
