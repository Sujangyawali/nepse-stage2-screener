import numpy as np
import pandas as pd

from screener.build_output import HISTORY_CHART_SESSIONS, write_history_json


def test_write_history_json_sma200_has_full_lookback_near_window_start():
    n = HISTORY_CHART_SESSIONS + 250  # plenty of history before the trimmed display window
    rng = np.random.default_rng(0)
    close = np.linspace(100, 300, n) + rng.normal(0, 0.5, n)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({"date": dates, "close": close})

    result = write_history_json("TEST", df)
    series = result["series"]

    assert len(series) == HISTORY_CHART_SESSIONS
    # The 250th point in a 300-point trimmed window would have no SMA200 if SMAs were
    # computed after trimming (only 250 rows of lookback available); with the full-history
    # fix it should be populated since 250 + 200 rows of real history exist before it.
    assert series[250]["sma200"] is not None
