from quant_guard.backtest.report import _max_drawdown_pct, _profit_total_pct, extract_metrics


def test_backtest_metric_pct_fields():
    s = {
        "profit_total": -0.37667258082,
        "max_drawdown_account": 0.3873659236978234,
        "max_drawdown_abs": 387.7708784399995,
        "total_trades": 1897,
        "wins": 998,
        "backtest_start": "2025-06-01",
        "backtest_end": "2026-06-01",
    }
    assert _profit_total_pct(s) == -37.667258082
    assert _max_drawdown_pct(s) == 38.73659236978234

    metrics = extract_metrics({"strategy": {"RsiReversalStrategy": s}})
    assert metrics.total_profit_pct == -37.667258082
    assert metrics.max_drawdown_pct == 38.73659236978234
