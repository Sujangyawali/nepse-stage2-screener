import json
from datetime import datetime

from scraper.config import DOCS_DATA_DIR, TIMEZONE
from scraper.sector_filter import load_symbols_meta
from scraper.storage import known_symbols, load_history
from screener.indicators import moving_average
from screener.trend_template import METHODS, evaluate
from screener.universe import compute_rs_score, rank_universe

RS_TOP_PERCENTILE_THRESHOLD = 70  # "top 30%" of the universe
CANDIDATE_SCORE_THRESHOLD = 8  # all 8 criteria must pass by default

HISTORY_CHART_SESSIONS = 300
MA_WINDOWS = (50, 150, 200)


def _equity_symbols_with_history() -> list:
    meta = load_symbols_meta()
    symbols = known_symbols()
    return [s for s in symbols if meta.get(s, {}).get("is_equity", False)]


def _build_method_block(method: str, symbols: list, histories: dict, meta: dict, rs_percentiles: dict) -> tuple:
    """Evaluate every symbol under one Trend Template variant (sma or ama). SMA and AMA
    candidacy are fully independent — a stock can pass one and fail the other."""
    stocks = []
    as_of_dates = []
    for sym in symbols:
        df = histories[sym]
        result = evaluate(df, method=method)
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

    # Relative strength is method-independent (based on raw price returns, not moving
    # averages), so it's computed once and reused by both the sma and ama blocks.
    rs_scores = {
        sym: compute_rs_score(histories[sym]["close"]) if len(histories[sym]) else None
        for sym in symbols
    }
    rs_percentiles = rank_universe(rs_scores)

    blocks = {}
    all_as_of_dates = []
    for method in METHODS:
        block, as_of_dates = _build_method_block(method, symbols, histories, meta, rs_percentiles)
        blocks[method] = block
        all_as_of_dates.extend(as_of_dates)

    as_of_trading_date = max(all_as_of_dates).strftime("%Y-%m-%d") if all_as_of_dates else None

    return {
        "generated_at": datetime.now(TIMEZONE).isoformat(),
        "as_of_trading_date": as_of_trading_date,
        **blocks,
    }, histories


def write_history_json(symbol: str, df) -> dict:
    # Compute moving averages on the full history first so the trailing display window's
    # early points still get a full lookback (e.g. a 200-window MA needs 200 prior rows) —
    # trimming before computing would starve the first ~200 chart points of their value.
    full_close = df["close"]
    ma_full = {
        (method, window): moving_average(full_close, window, method)
        for method in METHODS
        for window in MA_WINDOWS
    }

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
        for method in METHODS:
            for window in MA_WINDOWS:
                value = ma_tail[(method, window)][i]
                entry[f"{method}{window}"] = None if pd_isna(value) else float(value)
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
        "universe_size": candidates["sma"]["universe_size"],
        "sma_candidates_count": candidates["sma"]["candidates_count"],
        "ama_candidates_count": candidates["ama"]["candidates_count"],
    }
    (DOCS_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))

    if write_history_for_all:
        symbols_to_chart = set(histories.keys())
    else:
        symbols_to_chart = set()
        for method in METHODS:
            symbols_to_chart |= {s["symbol"] for s in candidates[method]["stocks"] if s["is_candidate"]}

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
        f"universe_size={result['sma']['universe_size']} "
        f"sma_candidates={result['sma']['candidates_count']} "
        f"ama_candidates={result['ama']['candidates_count']} "
        f"as_of={result['as_of_trading_date']}"
    )
