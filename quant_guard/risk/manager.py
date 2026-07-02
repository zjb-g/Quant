"""quant_guard.risk.manager: 统一风控入口。

所有下单路径必须经过 RiskManager.check_order()。
T3.1-T3.5 的风控逻辑在此整合。
"""

from datetime import datetime, timezone
from typing import List, Optional

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


class RiskManager:
    """统一风控管理器。

    所有订单必须经过 check_order() 检查后才能提交到交易所。

    用法：
        rm = RiskManager(config)
        decision = rm.check_order(order_request, account_state, market_state)
        if decision.allowed:
            # 提交订单
        else:
            # 拒绝，记录原因
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()
        self.state = RiskState()
        self._alert_callbacks: List = []

    def add_alert_callback(self, callback) -> None:
        """添加告警回调函数。"""
        self._alert_callbacks.append(callback)

    def _emit_alert(self, level: str, alert_type: str, message: str) -> None:
        """触发告警回调。"""
        for cb in self._alert_callbacks:
            try:
                cb(level, alert_type, message)
            except Exception:
                pass  # 告警回调失败不影响风控逻辑

    # ------------------------------------------------------------------ #
    # 核心方法
    # ------------------------------------------------------------------ #

    def check_order(
        self,
        order_request: dict,
        account_state: dict,
        market_state: dict,
    ) -> RiskDecision:
        """检查订单是否通过风控。

        参数：
            order_request: 订单请求，含：
                - symbol: 交易对
                - side: long/short
                - notional: 名义价值（USDT）
                - leverage: 杠杆
                - is_reduce_only: 是否仅减仓
            account_state: 账户状态，含：
                - current_total_notional: 当前总敞口
                - symbol_notionals: {symbol: notional} 各币敞口
            market_state: 市场状态，含：
                - liquidation_distance_pct: 强平距离百分比

        返回：
            RiskDecision: allow / reject / reduce_only / emergency_stop
        """
        # 检查每日重置
        self.state.check_daily_reset()

        # 1. Kill switch 检查（最高优先级）
        if self.state.kill_switch_active:
            is_reduce = order_request.get("is_reduce_only", False)
            if not is_reduce:
                decision = RiskDecision(
                    action=DecisionAction.REJECT,
                    reason=f"kill switch active: {self.state.kill_switch_reason}",
                    rule_id="RISK-10",
                )
                self._emit_alert("CRITICAL", "kill_switch_block", decision.reason)
                return decision
            # kill switch 激活时仍允许 reduce-only

        # 2. 回撤熔断检查（RISK-05）
        dd = self.state.current_drawdown_pct
        dd_decision = check_max_drawdown(dd, self.config)
        if dd_decision:
            self._emit_alert("CRITICAL", "max_drawdown_stop", dd_decision.reason)
            # 触发 kill switch
            self.state.activate_kill_switch(dd_decision.reason)
            is_reduce = order_request.get("is_reduce_only", False)
            if not is_reduce:
                return dd_decision

        # 3. 每日亏损检查（RISK-11）
        dl = self.state.daily_loss_pct
        dl_decision = check_daily_loss(dl, self.config)
        if dl_decision:
            self._emit_alert("CRITICAL", "daily_loss_stop", dl_decision.reason)
            self.state.activate_kill_switch(dl_decision.reason)
            is_reduce_dl = order_request.get("is_reduce_only", False)
            if not is_reduce_dl:
                return dl_decision

        # 以下检查对 reduce-only 跳过部分（减仓总是相对安全）
        is_reduce = order_request.get("is_reduce_only", False)
        symbol = order_request.get("symbol", "")
        notional = order_request.get("notional", 0)
        leverage = order_request.get("leverage", 1)

        # 4. 单笔下单上限（RISK-01）— reduce-only 跳过
        if not is_reduce:
            d = check_single_order_notional(notional, self.config)
            if d:
                self._emit_alert("WARNING", "risk_rejected", d.reason)
                return d

        # 5. 单币敞口（RISK-02）— FAIL-CLOSED: 缺失 account_state 或字段时拒绝
        if not isinstance(account_state, dict) or "symbol_notionals" not in account_state:
            d = RiskDecision(
                action=DecisionAction.REJECT,
                reason="风控数据不可用：account_state.symbol_notionals 缺失",
                rule_id="RISK-02",
            )
            self._emit_alert("CRITICAL", "risk_data_missing", d.reason)
            return d
        current_symbol_notional = account_state.get("symbol_notionals", {}).get(symbol, 0)
        d = check_symbol_exposure(
            symbol, notional, current_symbol_notional, self.config, is_reduce
        )
        if d:
            self._emit_alert("WARNING", "risk_rejected", d.reason)
            return d

        # 6. 总敞口（RISK-03）— FAIL-CLOSED: 缺失时拒绝
        if "current_total_notional" not in account_state:
            d = RiskDecision(
                action=DecisionAction.REJECT,
                reason="风控数据不可用：account_state.current_total_notional 缺失",
                rule_id="RISK-03",
            )
            self._emit_alert("CRITICAL", "risk_data_missing", d.reason)
            return d
        current_total = account_state.get("current_total_notional", 0)
        d = check_total_exposure(notional, current_total, self.config, is_reduce)
        if d:
            self._emit_alert("WARNING", "risk_rejected", d.reason)
            return d

        # 7. 杠杆上限（RISK-03）
        d = check_leverage(leverage, self.config)
        if d:
            self._emit_alert("WARNING", "risk_rejected", d.reason)
            return d

        # 8. 强平距离（RISK-04）— FAIL-CLOSED: 缺失时拒绝
        if not isinstance(market_state, dict) or "liquidation_distance_pct" not in market_state:
            d = RiskDecision(
                action=DecisionAction.REJECT,
                reason="风控数据不可用：market_state.liquidation_distance_pct 缺失",
                rule_id="RISK-04",
            )
            self._emit_alert("CRITICAL", "risk_data_missing", d.reason)
            return d
        liq_dist = market_state.get("liquidation_distance_pct", 100.0)
        d = check_liquidation_distance(liq_dist, self.config, is_reduce)
        if d:
            self._emit_alert("WARNING", "liquidation_warning", d.reason)
            return d

        # 全部通过
        return RiskDecision(action=DecisionAction.ALLOW, reason="all checks passed")

    # ------------------------------------------------------------------ #
    # Kill switch（T3.5）
    # ------------------------------------------------------------------ #

    def activate_kill_switch(self, reason: str) -> None:
        """激活 kill switch（RISK-10）。

        激活后所有新开仓请求被拒绝，仅允许 reduce-only 平仓。
        """
        self.state.activate_kill_switch(reason)
        self._emit_alert("CRITICAL", "kill_switch_activated", f"kill switch: {reason}")

    def deactivate_kill_switch(self) -> None:
        """解除 kill switch（谨慎操作）。"""
        self.state.deactivate_kill_switch()
        self._emit_alert("INFO", "kill_switch_deactivated", "kill switch deactivated")

    @property
    def is_kill_switch_active(self) -> bool:
        """kill switch 是否激活。"""
        return self.state.kill_switch_active

    # ------------------------------------------------------------------ #
    # 状态更新
    # ------------------------------------------------------------------ #

    def update_equity(self, equity: float) -> None:
        """更新权益（供定时同步调用）。"""
        self.state.update_equity(equity)

    def record_realized_pnl(self, pnl: float) -> None:
        """记录已实现盈亏。"""
        self.state.record_realized_pnl(pnl)

    def get_state_dict(self) -> dict:
        """获取风控状态字典（供 API）。"""
        return {
            **self.state.to_dict(),
            "max_leverage": self.config.max_leverage,
            "max_total_notional": self.config.max_total_notional,
        }

    def get_config_dict(self) -> dict:
        """获取风控配置字典（供 API）。"""
        return self.config.to_dict()

    def update_config(self, config: RiskConfig) -> None:
        """更新风控配置。"""
        self.config = config
