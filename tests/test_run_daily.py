import json

import scripts.run_daily as run_daily


def test_noop_when_as_of_date_unchanged(tmp_path, monkeypatch):
    last_run_path = tmp_path / "last_run.json"
    last_run_path.write_text(json.dumps({"last_trading_date": "2026-07-23"}))
    monkeypatch.setattr(run_daily, "LAST_RUN_PATH", last_run_path)
    monkeypatch.setattr(run_daily, "fetch_today_html", lambda: "<html></html>")
    monkeypatch.setattr(run_daily, "parse_as_of_date", lambda html: "2026-07-23")

    called = {"screener_ran": False}
    monkeypatch.setattr(run_daily, "run_screener", lambda **kw: called.update(screener_ran=True))

    exit_code = run_daily.main()

    assert exit_code == 0
    assert called["screener_ran"] is False


def test_runs_pipeline_when_new_trading_session(tmp_path, monkeypatch):
    last_run_path = tmp_path / "last_run.json"
    last_run_path.write_text(json.dumps({"last_trading_date": "2026-07-22"}))
    monkeypatch.setattr(run_daily, "LAST_RUN_PATH", last_run_path)
    monkeypatch.setattr(run_daily, "fetch_today_html", lambda: "<html></html>")
    monkeypatch.setattr(run_daily, "parse_as_of_date", lambda html: "2026-07-23")
    monkeypatch.setattr(run_daily, "parse_today_rows", lambda html: [{"symbol": "TEST", "name": "Test"}])
    monkeypatch.setattr(run_daily, "normalize_rows", lambda rows: [
        {"symbol": "TEST", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 100}
    ])

    upserted = []
    monkeypatch.setattr(run_daily, "upsert_rows", lambda symbol, rows: upserted.append((symbol, rows)))
    monkeypatch.setattr(
        run_daily, "run_screener", lambda **kw: {"universe_size": 1, "candidates_count": 0}
    )

    exit_code = run_daily.main()

    assert exit_code == 0
    assert upserted == [("TEST", [{
        "date": "2026-07-23", "open": 1, "high": 2, "low": 1, "close": 1.5,
        "volume": 100, "source": "daily_scrape",
    }])]
    assert json.loads(last_run_path.read_text())["last_trading_date"] == "2026-07-23"
