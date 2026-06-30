from quant_guard.services.equity_service import compute_equity_curve, infer_base_equity_from_balance


def test_compute_equity_curve_basic():
    rows = [
        {
            "close_time": "2025-06-01T12:00:00+00:00",
            "pnl": 10,
            "fee": 1,
            "funding_fee": 0.5,
        },
        {
            "close_time": "2025-06-02T12:00:00+00:00",
            "pnl": -5,
            "fee": 0.5,
            "funding_fee": 0,
        },
    ]
    curve = compute_equity_curve(rows, days=9999, base_equity=1000.0)
    assert len(curve) == 2
    assert curve[0]["equity"] == 1008.5
    assert curve[1]["equity"] == 1003.0
    assert curve[1]["drawdown_pct"] >= 0


def test_infer_base_equity():
    assert infer_base_equity_from_balance(10, 5) == 15
    assert infer_base_equity_from_balance(0, 0) == 1000.0
