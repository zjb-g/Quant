from quant_guard.services.trade_analysis_service import analyze_positions, filter_positions, sort_positions


def test_analyze_positions_basic():
    rows = [
        {
            "position_id": "1",
            "symbol": "ETH-USDT-SWAP",
            "side": "long",
            "leverage": 5,
            "pnl": 10,
            "fee": 1,
            "funding_fee": 0.5,
            "close_type": "full",
            "open_time": "2025-01-01T00:00:00+00:00",
            "close_time": "2025-01-01T02:00:00+00:00",
        },
        {
            "position_id": "2",
            "symbol": "ETH-USDT-SWAP",
            "side": "short",
            "leverage": 3,
            "pnl": -5,
            "fee": 0.8,
            "funding_fee": 0.2,
            "close_type": "full",
            "open_time": "2025-01-02T00:00:00+00:00",
            "close_time": "2025-01-02T05:00:00+00:00",
        },
    ]
    stats = analyze_positions(rows)
    assert stats["total_trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == 50.0
    assert stats["total_pnl"] == 5.0
    assert len(stats["by_side"]) == 2


def test_filter_and_sort_positions():
    rows = [
        {"position_id": "a", "symbol": "ETH-USDT-SWAP", "side": "long", "pnl": 1,
         "open_time": "2025-01-01T00:00:00+00:00", "close_time": "2025-01-01T01:00:00+00:00"},
        {"position_id": "b", "symbol": "BTC-USDT-SWAP", "side": "short", "pnl": -3,
         "open_time": "2025-01-02T00:00:00+00:00", "close_time": "2025-01-02T01:00:00+00:00"},
    ]
    filtered = filter_positions(rows, symbol="ETH-USDT-SWAP")
    assert len(filtered) == 1
    filtered_eth = filter_positions(rows, symbol="ETH")
    assert len(filtered_eth) == 1
    sorted_rows = sort_positions(rows, sort_by="pnl", order="asc")
    assert sorted_rows[0]["position_id"] == "b"


def test_kline_interval_boundaries():
    from quant_guard.services.kline_service import (
        ceil_to_interval,
        compute_chart_window_ms,
        floor_to_interval,
        interval_to_ms,
    )

    assert interval_to_ms("15m") == 900_000
    assert interval_to_ms("1d") == 86_400_000
    ts = 1_748_965_500_000  # arbitrary ms
    floored = floor_to_interval(ts, "15m")
    ceiled = ceil_to_interval(ts, "15m")
    assert floored <= ts <= ceiled
    start, end = compute_chart_window_ms(
        [{"open_time": "2025-06-01T00:00:00+00:00", "close_time": "2025-06-02T00:00:00+00:00"}],
        "1d",
    )
    assert start is not None and end is not None
    assert end > start
