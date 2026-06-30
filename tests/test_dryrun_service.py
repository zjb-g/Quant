from quant_guard.services.dryrun_service import get_dryrun_open_trades, get_dryrun_summary


def test_get_dryrun_summary_with_db():
    s = get_dryrun_summary()
    assert s.starting_balance == 1000.0
    assert s.open_trades >= 0


def test_get_dryrun_open_trades_shape():
    trades = get_dryrun_open_trades()
    for t in trades:
        assert t.pair
        assert t.side in ("long", "short")
        assert t.amount > 0
