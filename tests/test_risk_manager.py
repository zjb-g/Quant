"""tests/test_risk_manager: RiskManager 风控系统测试。

覆盖 T3.1-T3.5：基础结构、仓位/敞口/杠杆限制、强平距离、回撤熔断、
每日亏损限额、kill switch、紧急全平。
"""

import pytest
from datetime import datetime, timedelta, timezone

from quant_guard.risk.manager import RiskManager
from quant_guard.risk.rules import (
    DecisionAction,
    RiskConfig,
    RiskDecision,
    check_daily_loss,
    check_leverage,
    check_liquidation_distance,
    check_max_drawdown,
    check_single_order_notional,
    check_symbol_exposure,
    check_total_exposure,
)
from quant_guard.risk.state import RiskState


# ---------------------------------------------------------------------- #
# T3.1 RiskManager 基础结构
# ---------------------------------------------------------------------- #

def test_risk_manager_init():
    """RiskManager 可实例化，含默认配置。"""
    rm = RiskManager()
    assert rm.config.max_leverage == 5
    assert rm.config.max_total_notional == 1000
    assert rm.state.kill_switch_active is False


def test_check_order_returns_decision():
    """check_order 返回 RiskDecision。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "side": "long", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert isinstance(decision, RiskDecision)
    assert decision.action == DecisionAction.ALLOW


def test_custom_config():
    """自定义配置生效。"""
    config = RiskConfig(max_leverage=3, max_total_notional=500)
    rm = RiskManager(config)
    assert rm.config.max_leverage == 3
    assert rm.config.max_total_notional == 500


# ---------------------------------------------------------------------- #
# T3.2 仓位/敞口/杠杆限制
# ---------------------------------------------------------------------- #

def test_single_order_notional_rejected():
    """单笔下单超限被拒绝。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 300, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REJECT
    assert "RISK-01" in decision.rule_id


def test_symbol_exposure_rejected():
    """单币敞口超限被拒绝。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 200, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 200, "symbol_notionals": {"BTC/USDT:USDT": 200}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REJECT
    assert "RISK-02" in decision.rule_id


def test_total_exposure_rejected():
    """总敞口超限被拒绝。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 200, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 900, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REJECT
    assert "RISK-03" in decision.rule_id


def test_leverage_rejected():
    """杠杆超限被拒绝。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 10, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REJECT
    assert "RISK-03" in decision.rule_id


def test_reduce_only_bypasses_exposure_checks():
    """reduce-only 跳过敞口检查。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 500, "leverage": 3, "is_reduce_only": True}
    account = {"current_total_notional": 900, "symbol_notionals": {"BTC/USDT:USDT": 300}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


# ---------------------------------------------------------------------- #
# T3.3 强平距离实时风控
# ---------------------------------------------------------------------- #

def test_liquidation_distance_reduce_only():
    """强平距离低时返回 reduce_only。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 5}  # 低于阈值 10%
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REDUCE_ONLY
    assert "RISK-04" in decision.rule_id


def test_liquidation_distance_reduce_only_allows_reduce():
    """强平距离低时 reduce-only 仍允许。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": True}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 5}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


def test_liquidation_distance_safe_allows():
    """强平距离安全时允许开仓。"""
    rm = RiskManager()
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


# ---------------------------------------------------------------------- #
# T3.4 回撤熔断与每日亏损限额
# ---------------------------------------------------------------------- #

def test_max_drawdown_triggers_emergency_stop():
    """最大回撤超限触发 emergency_stop。"""
    rm = RiskManager()
    rm.state.current_date = "2026-06-29"
    rm.state.equity_high_watermark = 1000
    rm.state.current_equity = 800  # 回撤 20% > 15%
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.EMERGENCY_STOP
    assert "RISK-05" in decision.rule_id


def test_max_drawdown_allows_reduce_only():
    """最大回撤超限时 reduce-only 仍允许。"""
    rm = RiskManager()
    rm.state.current_date = "2026-06-29"
    rm.state.equity_high_watermark = 1000
    rm.state.current_equity = 800
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": True}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


def test_daily_loss_triggers_emergency_stop():
    """每日亏损超限触发 emergency_stop。"""
    from datetime import datetime, timezone

    rm = RiskManager()
    rm.state.current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rm.state.daily_start_equity = 1000
    rm.state.current_equity = 940  # 日亏 6% > 5%
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.EMERGENCY_STOP
    assert "RISK-11" in decision.rule_id


def test_drawdown_triggers_kill_switch():
    """回撤超限自动激活 kill switch。"""
    rm = RiskManager()
    rm.state.current_date = "2026-06-29"
    rm.state.equity_high_watermark = 1000
    rm.state.current_equity = 800
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    rm.check_order(order, account, market)
    assert rm.state.kill_switch_active is True


# ---------------------------------------------------------------------- #
# T3.5 Kill Switch
# ---------------------------------------------------------------------- #

def test_kill_switch_rejects_new_orders():
    """kill switch 激活后拒绝新开仓。"""
    rm = RiskManager()
    rm.activate_kill_switch("test")
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.REJECT
    assert "RISK-10" in decision.rule_id


def test_kill_switch_allows_reduce_only():
    """kill switch 激活后仍允许 reduce-only。"""
    rm = RiskManager()
    rm.activate_kill_switch("test")
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": True}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


def test_kill_switch_deactivate():
    """解除 kill switch 后恢复正常。"""
    rm = RiskManager()
    rm.activate_kill_switch("test")
    assert rm.is_kill_switch_active is True
    rm.deactivate_kill_switch()
    assert rm.is_kill_switch_active is False
    order = {"symbol": "BTC/USDT:USDT", "notional": 100, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    decision = rm.check_order(order, account, market)
    assert decision.action == DecisionAction.ALLOW


def test_kill_switch_records_reason():
    """kill switch 记录原因和时间。"""
    rm = RiskManager()
    rm.activate_kill_switch("manual test")
    assert rm.state.kill_switch_reason == "manual test"
    assert rm.state.kill_switch_activated_at is not None


# ---------------------------------------------------------------------- #
# 告警回调
# ---------------------------------------------------------------------- #

def test_alert_callback_called():
    """风控触发时调用告警回调。"""
    alerts = []
    rm = RiskManager()
    rm.add_alert_callback(lambda level, atype, msg: alerts.append((level, atype, msg)))
    rm.activate_kill_switch("test")
    assert len(alerts) >= 1
    assert alerts[0][0] == "CRITICAL"


def test_alert_on_reject():
    """订单被拒时触发告警。"""
    alerts = []
    rm = RiskManager()
    rm.add_alert_callback(lambda level, atype, msg: alerts.append((level, atype, msg)))
    order = {"symbol": "BTC/USDT:USDT", "notional": 500, "leverage": 3, "is_reduce_only": False}
    account = {"current_total_notional": 0, "symbol_notionals": {}}
    market = {"liquidation_distance_pct": 50}
    rm.check_order(order, account, market)
    assert any(a[1] == "risk_rejected" for a in alerts)


# ---------------------------------------------------------------------- #
# RiskState 测试
# ---------------------------------------------------------------------- #

def test_state_daily_reset():
    """跨日重置每日统计。"""
    state = RiskState()
    state.current_date = "2026-06-28"
    state.daily_start_equity = 1000
    state.current_equity = 950
    state.daily_realized_pnl = -50

    # 模拟跨日
    reset = state.check_daily_reset(datetime(2026, 6, 29, tzinfo=timezone.utc))
    assert reset is True
    assert state.daily_start_equity == 950  # 重置为当前权益
    assert state.daily_realized_pnl == 0


def test_state_no_reset_same_day():
    """同日不重置。"""
    state = RiskState()
    state.current_date = "2026-06-29"
    reset = state.check_daily_reset(datetime(2026, 6, 29, tzinfo=timezone.utc))
    assert reset is False


def test_state_drawdown_calculation():
    """回撤计算正确。"""
    state = RiskState()
    state.equity_high_watermark = 1000
    state.current_equity = 850
    assert state.current_drawdown_pct == 15.0


def test_state_daily_loss_calculation():
    """每日亏损计算正确。"""
    state = RiskState()
    state.daily_start_equity = 1000
    state.current_equity = 960
    assert state.daily_loss_pct == 4.0
