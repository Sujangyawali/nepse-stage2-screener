import pandas as pd

from screener.universe import compute_rs_score, rank_universe


def test_compute_rs_score_none_when_too_short():
    close = pd.Series(range(1, 50), dtype=float)  # shorter than the smallest RS window (65)
    assert compute_rs_score(close) is None


def test_compute_rs_score_positive_for_uptrend():
    close = pd.Series(range(1, 300), dtype=float)
    score = compute_rs_score(close)
    assert score > 0


def test_compute_rs_score_negative_for_downtrend():
    close = pd.Series(range(300, 1, -1), dtype=float)
    score = compute_rs_score(close)
    assert score < 0


def test_rank_universe_orders_best_performer_highest():
    scores = {"WORST": -0.5, "MID": 0.0, "BEST": 0.5}
    percentiles = rank_universe(scores)
    assert percentiles["BEST"] == 100.0
    assert percentiles["WORST"] == 0.0
    assert percentiles["MID"] == 50.0


def test_rank_universe_excludes_none_scores_from_ranking():
    scores = {"A": 0.1, "B": None, "C": 0.2}
    percentiles = rank_universe(scores)
    assert percentiles["B"] is None
    assert percentiles["A"] == 0.0
    assert percentiles["C"] == 100.0
