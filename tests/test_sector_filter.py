from scraper.sector_filter import is_equity_sector


def test_excludes_mutual_fund():
    assert is_equity_sector("Mutual Fund") is False


def test_excludes_promoter_share():
    assert is_equity_sector("Promoter Share") is False


def test_excludes_corporate_debentures():
    assert is_equity_sector("Corporate Debentures") is False


def test_includes_commercial_bank():
    assert is_equity_sector("Commercial Bank") is True


def test_includes_microfinance():
    assert is_equity_sector("Microfinance") is True
