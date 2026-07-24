import pandas as pd

from screener.indicators import is_trending_up, sma, week52_high_low


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
