import numpy as np
import pandas as pd

from screener.market import equal_weight_index, market_direction


def _histories(n_stocks, path):
    dates = pd.date_range("2025-01-01", periods=len(path), freq="D")
    rng = np.random.default_rng(0)
    out = {}
    for i in range(n_stocks):
        noise = np.exp(rng.normal(0, 0.002, len(path)))
        out[f"S{i}"] = pd.DataFrame({"date": dates, "close": np.asarray(path) * noise})
    return out


def test_uptrend_when_index_above_rising_average():
    m = market_direction(_histories(120, np.linspace(100, 200, 120)))
    assert m["status"] == "uptrend"
    assert m["ma50_rising"] is True and m["pct_vs_ma50"] > 0


def test_correction_when_index_below_falling_average():
    m = market_direction(_histories(120, np.linspace(200, 100, 120)))
    assert m["status"] == "correction"


def test_caution_on_rally_inside_downtrend():
    path = np.concatenate([np.linspace(200, 100, 110), np.linspace(100, 125, 10)])
    m = market_direction(_histories(120, path))
    assert m["status"] == "caution"  # above a still-falling average


def test_corporate_action_gaps_do_not_move_the_index():
    hist = _histories(120, np.full(80, 100.0))
    gapped = hist["S0"].copy()
    gapped.loc[40:, "close"] = gapped.loc[40:, "close"] * 0.5  # 50% ex-bonus cliff in one stock
    hist["S0"] = gapped
    idx = equal_weight_index(hist)["index"]
    assert abs(idx.iloc[-1] / idx.iloc[0] - 1) < 0.01
