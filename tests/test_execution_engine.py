"""tests/test_execution_engine: 执行引擎测试。"""

import pytest

from quant_guard.execution.engine import ExecutionEngine
from quant_guard.execution.idempotency import IdempotencyManager
from quant_guard.execution.order_manager import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from quant_guard.risk.manager import RiskManager


# ---------------------------------------------------------------------- #
# 订单模型
# ---------------------------------------------------------------------- #

def test_order_request_creation():
    """订单请求创建。"""
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.01,
        order_type=OrderType.MARKET,
        price=60000,
    )
    assert order.symbol == "BTC/USDT:USDT"
    assert order.side == OrderSide.BUY
    assert order.notional == pytest.approx(600)  # 0.01 * 60000


def test_order_request_reduce_only():
    """reduce_only 标记。"""
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.SELL,
        amount=0.01,
        reduce_only=True,
    )
    assert order.reduce_only is True


def test_order_to_risk_check_dict():
    """订单转风控检查字典。"""
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.01,
        price=60000,
        leverage=5,
    )
    d = order.to_risk_check_dict()
    assert d["symbol"] == "BTC/USDT:USDT"
    assert d["notional"] == pytest.approx(600)
    assert d["leverage"] == 5
    assert d["is_reduce_only"] is False


# ---------------------------------------------------------------------- #
# 幂等模块
# ---------------------------------------------------------------------- #

def test_generate_client_order_id_deterministic():
    """相同输入生成相同 ID。"""
    id1 = IdempotencyManager.generate_client_order_id(
        "strat", "BTC/USDT:USDT", "buy", "sig1", 1000
    )
    id2 = IdempotencyManager.generate_client_order_id(
        "strat", "BTC/USDT:USDT", "buy", "sig1", 1000
    )
    assert id1 == id2


def test_generate_client_order_id_different_signal():
    """不同信号生成不同 ID。"""
    id1 = IdempotencyManager.generate_client_order_id(
        "strat", "BTC/USDT:USDT", "buy", "sig1", 1000
    )
    id2 = IdempotencyManager.generate_client_order_id(
        "strat", "BTC/USDT:USDT", "buy", "sig2", 1000
    )
    assert id1 != id2


def test_idempotency_check_and_mark():
    """幂等检查与标记。"""
    mgr = IdempotencyManager()
    assert mgr.check_and_mark("id1") is True  # 首次
    assert mgr.check_and_mark("id1") is False  # 重复
    assert mgr.check_and_mark("id2") is True  # 不同 ID
    assert mgr.count == 2


def test_idempotency_is_submitted():
    """检查已提交状态。"""
    mgr = IdempotencyManager()
    mgr.mark_submitted("abc")
    assert mgr.is_submitted("abc") is True
    assert mgr.is_submitted("xyz") is False


# ---------------------------------------------------------------------- #
# ExecutionEngine
# ---------------------------------------------------------------------- #

def test_dry_run_order_filled():
    """dry-run 模式订单成交。"""
    rm = RiskManager()
    engine = ExecutionEngine(risk_manager=rm, dry_run=True)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.001,
        price=60000,
        leverage=3,
        strategy_id="test",
        signal_id="sig1",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    result = engine.submit_order(order, account, market)
    assert result.status == OrderStatus.FILLED
    assert result.is_filled


def test_risk_rejected_order():
    """风控拒绝的订单不执行。"""
    rm = RiskManager()
    engine = ExecutionEngine(risk_manager=rm, dry_run=True)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.01,
        price=60000,
        leverage=10,  # 超过 5x 上限
        strategy_id="test",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    result = engine.submit_order(order, account, market)
    assert result.status == OrderStatus.REJECTED
    assert "risk rejected" in result.error


def test_duplicate_order_skipped():
    """重复订单被跳过。"""
    rm = RiskManager()
    engine = ExecutionEngine(risk_manager=rm, dry_run=True)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.001,
        price=60000,
        leverage=3,
        strategy_id="test",
        signal_id="sig1",
        client_order_id="fixed_id_123",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}

    r1 = engine.submit_order(order, account, market)
    assert r1.is_filled

    r2 = engine.submit_order(order, account, market)
    assert r2.status == OrderStatus.REJECTED
    assert "duplicate" in r2.error


def test_live_not_confirmed_rejected():
    """live 模式未确认时拒绝下单。"""
    rm = RiskManager()
    engine = ExecutionEngine(risk_manager=rm, dry_run=False, live_confirmed=False)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.001,
        price=60000,
        leverage=3,
        strategy_id="test",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    result = engine.submit_order(order, account, market)
    assert result.status == OrderStatus.REJECTED
    assert "not confirmed" in result.error


def test_kill_switch_blocks_order():
    """kill switch 激活时阻止下单。"""
    rm = RiskManager()
    rm.activate_kill_switch("test")
    engine = ExecutionEngine(risk_manager=rm, dry_run=True)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        amount=0.001,
        price=60000,
        leverage=3,
        strategy_id="test",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    result = engine.submit_order(order, account, market)
    assert result.status == OrderStatus.REJECTED
    assert "kill switch" in result.error


def test_reduce_only_allowed_with_kill_switch():
    """kill switch 激活时 reduce-only 仍允许。"""
    rm = RiskManager()
    rm.activate_kill_switch("test")
    engine = ExecutionEngine(risk_manager=rm, dry_run=True)
    order = OrderRequest(
        symbol="BTC/USDT:USDT",
        side=OrderSide.SELL,
        amount=0.001,
        price=60000,
        leverage=3,
        reduce_only=True,
        strategy_id="test",
    )
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    result = engine.submit_order(order, account, market)
    assert result.is_filled
