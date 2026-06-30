from quant_guard.services.control_service import ControlService
from quant_guard.execution.order_manager import OrderStatus
from quant_guard.services.freqtrade_service import BotState


def _mock_stop_bot():
    return BotState(running=False, pid=None)


def test_kill_switch_blocks_bot_start(monkeypatch):
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.freqtrade_service.stop_bot",
        _mock_stop_bot,
    )
    svc = ControlService()
    svc.activate_kill_switch("test")
    assert svc.is_kill_switch_active()
    state = svc.get_api_risk_state()
    assert state["kill_switch"] is True
    assert state["kill_switch_reason"] == "test"


def test_emergency_close_no_positions(monkeypatch):
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.freqtrade_service.stop_bot",
        _mock_stop_bot,
    )
    svc = ControlService()

    class FakeClient:
        def get_positions(self):
            return []

    monkeypatch.setattr(
        "quant_guard.exchange.okx_client.OKXClient",
        lambda **_: FakeClient(),
    )
    result = svc.emergency_close_all(reason="test")
    assert result["closed"] == 0
    assert svc.is_kill_switch_active()


def test_emergency_close_dry_run_with_positions(monkeypatch):
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.freqtrade_service.stop_bot",
        _mock_stop_bot,
    )
    svc = ControlService()
    from quant_guard.exchange.models import Position, Side

    class FakeClient:
        def get_positions(self):
            return [
                Position(
                    symbol="BTC/USDT:USDT",
                    side=Side.LONG,
                    contracts=0.01,
                    entry_price=60000,
                    mark_price=61000,
                    leverage=3,
                    unrealized_pnl=10,
                )
            ]

    monkeypatch.setattr(
        "quant_guard.exchange.okx_client.OKXClient",
        lambda **_: FakeClient(),
    )
    monkeypatch.delenv("LIVE_TRADING_CONFIRMED", raising=False)
    result = svc.emergency_close_all(reason="test")
    assert result["dry_run"] is True
    assert result["attempted"] == 1
    assert result["results"][0]["status"] == OrderStatus.FILLED.value
