import numpy as np
import pandas as pd

from screener.indicators import is_trending_up, kama, moving_average, sma, week52_high_low


def test_sma_basic_window():
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, 3)
    assert result.isna().sum() == 2
    assert result.iloc[2] == 2  # mean(1,2,3)
    assert result.iloc[-1] == 4  # mean(3,4,5)


def test_sma_insufficient_data_is_all_nan():
    series = pd.Series([1, 2, 3])
    result = sma(series, 5)
    assert result.isna().all()


def test_is_trending_up_true_when_rising():
    series = pd.Series(range(1, 31), dtype=float)  # 1..30, monotonic
    assert is_trending_up(series, lookback=20) is True


def test_is_trending_up_false_when_falling():
    series = pd.Series(range(30, 0, -1), dtype=float)
    assert is_trending_up(series, lookback=20) is False


def test_is_trending_up_none_when_insufficient_history():
    series = pd.Series(range(1, 10), dtype=float)
    assert is_trending_up(series, lookback=20) is None


def test_week52_high_low_uses_trailing_window():
    close = pd.Series([50] * 10 + [200] + [100] * 224)  # spike buried far in the past
    high, low = week52_high_low(close, sessions=235)
    # window of last 235 covers the tail of the 50s, the 200 spike, and the 100s
    assert high == 200
    assert low == 50


def test_kama_nan_before_er_period():
    series = pd.Series(range(1, 6), dtype=float)  # shorter than default er_period=10
    result = kama(series)
    assert result.isna().all()


def test_kama_seeds_at_er_period_with_raw_price():
    series = pd.Series(range(1, 21), dtype=float)
    result = kama(series, er_period=10)
    assert result.iloc[10] == series.iloc[10]
    assert result.iloc[:10].isna().all()


def test_kama_tracks_closely_in_a_strong_consistent_trend():
    # Perfectly efficient trend (constant step size) -> efficiency ratio ~1 -> KAMA should
    # sit very close to price, unlike a slow-reacting SMA.
    series = pd.Series(np.arange(1, 101, dtype=float))
    result = kama(series, er_period=10, fast_period=2, slow_period=200)
    # A same-window SMA200 would sit ~50 away (the midpoint of a 1..100 ramp); KAMA in a
    # perfectly efficient trend should hug price far more closely than that.
    assert abs(result.iloc[-1] - series.iloc[-1]) < 5.0


def test_kama_lags_more_in_a_choppy_series():
    rng = np.random.default_rng(0)
    # Oscillate around a fixed level with no net direction -> efficiency ratio ~0 -> KAMA
    # should behave like the heavily-smoothed slow_period tier, far from the last price spike.
    series = pd.Series(100 + rng.normal(0, 5, 150))
    series.iloc[-1] = 200  # one big spike at the very end
    result = kama(series, er_period=10, fast_period=2, slow_period=200)
    assert abs(result.iloc[-1] - series.iloc[-1]) > 50


def test_moving_average_dispatches_sma():
    series = pd.Series(range(1, 60), dtype=float)
    assert moving_average(series, 10, "sma").equals(sma(series, 10))


def test_moving_average_dispatches_ama():
    series = pd.Series(range(1, 60), dtype=float)
    assert moving_average(series, 30, "ama").equals(kama(series, slow_period=30))


def test_moving_average_rejects_unknown_method():
    import pytest
    with pytest.raises(ValueError):
        moving_average(pd.Series([1.0, 2.0]), 10, "wma")
