import numpy as np
import pandas as pd

from screener.setups import analyze_base, evaluate_setup


def _bars(path, volume=None, start="2025-01-01"):
    """OHLCV frame from a close path: high/low hug the close by +/-0.5%."""
    close = np.asarray(path, dtype=float)
    vol = np.full(len(close), 10_000.0) if volume is None else np.asarray(volume, dtype=float)
    return pd.DataFrame({
        "date": pd.date_range(start, periods=len(close), freq="D"),
        "open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": vol,
    })


def _leg(a, b, n):
    return list(np.linspace(a, b, n))[1:]


def _vcp_path():
    # Advance into a peak at 200, then contractions of ~20%, ~10%, ~5% with rising lows,
    # finishing just under the last contraction's high (the pivot, ~195).
    path = list(np.linspace(100, 200, 120))
    path += _leg(200, 160, 12) + _leg(160, 196, 12)   # T1 ~20%
    path += _leg(196, 177, 8) + _leg(177, 195, 8)     # T2 ~10%
    path += _leg(195, 185, 6) + _leg(185, 192, 6)     # T3 ~5%
    return path


def test_analyze_base_finds_contracting_vcp_and_pivot():
    base = analyze_base(_bars(_vcp_path()))

    assert base is not None and base["is_vcp"] is True
    assert base["t_count"] == 3
    depths = base["contractions_pct"]
    assert depths == sorted(depths, reverse=True)
    assert 18 <= depths[0] <= 22 and depths[-1] <= 7
    assert 194 <= base["pivot"] <= 197  # high of the last contraction
    assert 0 < base["dist_to_pivot_pct"] < 5


def test_expanding_pullbacks_are_not_a_vcp():
    path = list(np.linspace(100, 200, 120))
    path += _leg(200, 190, 8) + _leg(190, 199, 8)    # 5%
    path += _leg(199, 180, 10) + _leg(180, 198, 10)  # ~10% (deeper -> not contracting)
    path += _leg(198, 160, 12) + _leg(160, 190, 12)  # ~19%
    base = analyze_base(_bars(path))

    assert base is not None and base["is_vcp"] is False


def test_stock_at_highs_has_no_base():
    assert analyze_base(_bars(np.linspace(100, 200, 150))) is None


def test_ready_status_near_pivot_with_stop_under_last_low():
    setup = evaluate_setup(_bars(_vcp_path()))

    assert setup["status"] == "ready"
    assert setup["stop"] < setup["pivot"]
    assert setup["risk_pct"] <= 8.0


def test_breakout_through_pivot_on_volume():
    path = _vcp_path()
    volume = [10_000.0] * len(path)
    path.append(path[-1] * 1.04)  # closes above the ~195 pivot
    volume.append(30_000.0)       # 3x average volume
    setup = evaluate_setup(_bars(path, volume))

    assert setup["status"] == "breakout"
    assert setup["breakout_type"] == "vcp_pivot"
    assert setup["breakout_volume_ratio"] >= 1.5


def test_breakout_on_weak_volume_is_flagged_low_volume():
    path = _vcp_path()
    volume = [10_000.0] * len(path)
    path.append(path[-1] * 1.04)
    volume.append(11_000.0)
    setup = evaluate_setup(_bars(path, volume))

    assert setup["status"] == "breakout_low_volume"


def test_new_high_during_a_run_is_not_a_breakout():
    # Making a new 52-week high every day (no consolidation) shouldn't trigger an entry.
    path = list(np.linspace(100, 200, 150))
    volume = [10_000.0] * 149 + [40_000.0]
    assert evaluate_setup(_bars(path, volume)) is None
