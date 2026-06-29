"""quant_guard.risk.rules: 风控规则定义。

定义 RISK-01 到 RISK-11 规则，每条规则返回 RiskDecision。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DecisionAction(str, Enum):
    """风控决策动作。"""

    ALLOW = "allow"
    REJECT = "reject"
    REDUCE_ONLY = "reduce_only"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class RiskDecision:
    """风控决策结果。"""

    action: DecisionAction
    reason: str = ""
    rule_id: str = ""

    @property
    def allowed(self) -> bool:
        """是否允许下单。"""
        return self.action == DecisionAction.ALLOW

    @property
    def rejected(self) -> bool:
        """是否拒绝。"""
        return self.action == DecisionAction.REJECT


@dataclass
class RiskConfig:
    """风控配置参数。

    默认值基于 ADR-004（≤1000 USDT 实盘规模）。
    """

    # RISK-01: 单笔下单名义价值上限
    max_single_order_notional: float = 200.0
    # RISK-02: 单币种敞口上限
    max_symbol_notional: float = 300.0
    # RISK-03: 总敞口上限
    max_total_notional: float = 1000.0
    # RISK-03: 最大杠杆
    max_leverage: int = 5
    # RISK-04: 强平距离阈值（%）
    liquidation_distance_pct: float = 10.0
    # RISK-05: 最大回撤熔断（%）
    max_drawdown_stop_pct: float = 15.0
    # RISK-11: 每日亏损限额（%）
    daily_loss_stop_pct: float = 5.0

    def to_dict(self) -> dict:
        return {
            "max_single_order_notional": self.max_single_order_notional,
            "max_symbol_notional": self.max_symbol_notional,
            "max_total_notional": self.max_total_notional,
            "max_leverage": self.max_leverage,
            "liquidation_distance_pct": self.liquidation_distance_pct,
            "max_drawdown_stop_pct": self.max_drawdown_stop_pct,
            "daily_loss_stop_pct": self.daily_loss_stop_pct,
        }


# ---------------------------------------------------------------------- #
# 规则检查函数
# ---------------------------------------------------------------------- #

def check_single_order_notional(
    order_notional: float, config: RiskConfig
) -> Optional[RiskDecision]:
    """RISK-01: 单笔下单名义价值上限。"""
    if order_notional > config.max_single_order_notional:
        return RiskDecision(
            action=DecisionAction.REJECT,
            reason=f"single order notional {order_notional} > limit {config.max_single_order_notional}",
            rule_id="RISK-01",
        )
    return None


def check_symbol_exposure(
    symbol: str,
    order_notional: float,
    current_symbol_notional: float,
    config: RiskConfig,
    is_reduce_only: bool = False,
) -> Optional[RiskDecision]:
    """RISK-02: 单币种敞口上限。"""
    if is_reduce_only:
        return None  # 减仓不检查敞口上限
    new_exposure = current_symbol_notional + order_notional
    if new_exposure > config.max_symbol_notional:
        return RiskDecision(
            action=DecisionAction.REJECT,
            reason=f"symbol {symbol} exposure {new_exposure} > limit {config.max_symbol_notional}",
            rule_id="RISK-02",
        )
    return None


def check_total_exposure(
    order_notional: float,
    current_total_notional: float,
    config: RiskConfig,
    is_reduce_only: bool = False,
) -> Optional[RiskDecision]:
    """RISK-03: 总敞口上限。"""
    if is_reduce_only:
        return None
    new_total = current_total_notional + order_notional
    if new_total > config.max_total_notional:
        return RiskDecision(
            action=DecisionAction.REJECT,
            reason=f"total exposure {new_total} > limit {config.max_total_notional}",
            rule_id="RISK-03",
        )
    return None


def check_leverage(
    leverage: float, config: RiskConfig
) -> Optional[RiskDecision]:
    """RISK-03: 杠杆上限。"""
    if leverage > config.max_leverage:
        return RiskDecision(
            action=DecisionAction.REJECT,
            reason=f"leverage {leverage}x > limit {config.max_leverage}x",
            rule_id="RISK-03",
        )
    return None


def check_liquidation_distance(
    liq_distance_pct: float,
    config: RiskConfig,
    is_reduce_only: bool = False,
) -> Optional[RiskDecision]:
    """RISK-04: 强平距离实时风控。

    强平距离低于阈值时禁止加仓，只允许 reduce-only。
    """
    if is_reduce_only:
        return None  # 减仓总是允许
    if liq_distance_pct < config.liquidation_distance_pct:
        return RiskDecision(
            action=DecisionAction.REDUCE_ONLY,
            reason=f"liquidation distance {liq_distance_pct:.1f}% < threshold {config.liquidation_distance_pct}%",
            rule_id="RISK-04",
        )
    return None


def check_max_drawdown(
    current_drawdown_pct: float, config: RiskConfig
) -> Optional[RiskDecision]:
    """RISK-05: 最大回撤熔断。"""
    if current_drawdown_pct >= config.max_drawdown_stop_pct:
        return RiskDecision(
            action=DecisionAction.EMERGENCY_STOP,
            reason=f"max drawdown {current_drawdown_pct:.1f}% >= limit {config.max_drawdown_stop_pct}%",
            rule_id="RISK-05",
        )
    return None


def check_daily_loss(
    daily_loss_pct: float, config: RiskConfig
) -> Optional[RiskDecision]:
    """RISK-11: 每日亏损限额。"""
    if daily_loss_pct >= config.daily_loss_stop_pct:
        return RiskDecision(
            action=DecisionAction.EMERGENCY_STOP,
            reason=f"daily loss {daily_loss_pct:.1f}% >= limit {config.daily_loss_stop_pct}%",
            rule_id="RISK-11",
        )
    return None
