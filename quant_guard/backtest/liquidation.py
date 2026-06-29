"""quant_guard.backtest.liquidation: 强平距离与强平模拟模块。

用标记价格估算强平风险和模拟强平事件。

重要说明：
- 这是保守估算模型，不是交易所精确公式。
- OKX 统一账户 + 双向持仓（ADR-003/005），实际强平价受全仓保证金影响。
- 保守模型假设逐仓（isolated），仅考虑单仓位保证金。
- 实盘前应以交易所返回的 liquidation_price 为准。

强平价格估算公式（逐仓，简化版）：
  多头强平价 = entry_price * (1 - 1/leverage + maintenance_margin_rate)
  空头强平价 = entry_price * (1 + 1/leverage - maintenance_margin_rate)

强平距离 = (mark_price - liquidation_price) / mark_price * 100%
  - 多头：mark 下跌接近 liq_price 时距离减小
  - 空头：mark 上涨接近 liq_price 时距离减小
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from quant_guard.exchange.models import Side


class MarginMode(str, Enum):
    """保证金模式。"""

    ISOLATED = "isolated"
    CROSS = "cross"


@dataclass(frozen=True)
class LiquidationEstimate:
    """强平估算结果。"""

    entry_price: float
    mark_price: float
    liquidation_price: float
    side: Side
    leverage: float
    margin_mode: MarginMode
    maintenance_margin_rate: float
    distance_pct: float  # 强平距离百分比（正数，越小越危险）
    is_liquidated: bool  # 是否已触发强平


def estimate_liquidation_price(
    entry_price: float,
    leverage: float,
    side: Side,
    margin_mode: MarginMode = MarginMode.ISOLATED,
    maintenance_margin_rate: float = 0.005,
) -> float:
    """估算强平价格（保守模型）。

    参数：
        entry_price: 开仓价格
        leverage: 杠杆倍数（如 5.0）
        side: 持仓方向
        margin_mode: 保证金模式（当前仅实现 isolated）
        maintenance_margin_rate: 维持保证金率（OKX 默认 0.5%）

    返回：
        估算的强平价格

    公式（保守，逐仓）：
        多头：liq = entry * (1 - 1/lev + mmr)
        空头：liq = entry * (1 + 1/lev - mmr)

    示例：
        # 多头，开仓 60000，5x 杠杆
        >>> estimate_liquidation_price(60000, 5, Side.LONG)
        48600.0  # 60000 * (1 - 0.2 + 0.005)
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if leverage <= 0:
        raise ValueError("leverage must be positive")
    if margin_mode != MarginMode.ISOLATED:
        # 逐仓模型用于保守估算，全仓模型更复杂（涉及全账户余额）
        # 保守起见用逐仓估算，实盘以交易所为准
        pass

    inv_leverage = 1.0 / leverage

    if side == Side.LONG:
        # 多头：价格下跌到 (1 - 1/lev + mmr) * entry 时强平
        liq_price = entry_price * (1.0 - inv_leverage + maintenance_margin_rate)
    else:
        # 空头：价格上涨到 (1 + 1/lev - mmr) * entry 时强平
        liq_price = entry_price * (1.0 + inv_leverage - maintenance_margin_rate)

    return round(liq_price, 8)


def liquidation_distance_pct(
    mark_price: float,
    liquidation_price: float,
    side: Side,
) -> float:
    """计算当前标记价格到强平价的距离百分比。

    参数：
        mark_price: 当前标记价格
        liquidation_price: 强平价格
        side: 持仓方向

    返回：
        强平距离百分比（正数，表示还有多远才强平）：
        - 多头：mark_price 高于 liq_price 时为正，低于时为负（已强平）
        - 空头：mark_price 低于 liq_price 时为正，高于时为负（已强平）

    示例：
        # 多头，mark=58000，liq=48600
        >>> liquidation_distance_pct(58000, 48600, Side.LONG)
        16.21  # 距离强平还有 16.21%
    """
    if mark_price <= 0:
        raise ValueError("mark_price must be positive")

    if side == Side.LONG:
        # 多头：(mark - liq) / mark，mark 越接近 liq 距离越小
        distance = (mark_price - liquidation_price) / mark_price * 100.0
    else:
        # 空头：(liq - mark) / mark，mark 越接近 liq 距离越小
        distance = (liquidation_price - mark_price) / mark_price * 100.0

    return round(distance, 4)


def should_trigger_liquidation(
    mark_price: float,
    liquidation_price: float,
    side: Side,
) -> bool:
    """判断是否应触发模拟强平。

    参数：
        mark_price: 当前标记价格
        liquidation_price: 强平价格
        side: 持仓方向

    返回：
        True 如果已穿越强平价（应强平）

    规则：
        - 多头：mark_price <= liquidation_price 时强平
        - 空头：mark_price >= liquidation_price 时强平
    """
    if side == Side.LONG:
        return mark_price <= liquidation_price
    else:
        return mark_price >= liquidation_price


def analyze_liquidation_risk(
    entry_price: float,
    mark_price: float,
    leverage: float,
    side: Side,
    margin_mode: MarginMode = MarginMode.ISOLATED,
    maintenance_margin_rate: float = 0.005,
) -> LiquidationEstimate:
    """综合分析强平风险，返回完整估算结果。

    参数：
        entry_price: 开仓价格
        mark_price: 当前标记价格
        leverage: 杠杆倍数
        side: 持仓方向
        margin_mode: 保证金模式
        maintenance_margin_rate: 维持保证金率

    返回：
        LiquidationEstimate，含强平价/距离/是否触发
    """
    liq_price = estimate_liquidation_price(
        entry_price, leverage, side, margin_mode, maintenance_margin_rate
    )
    distance = liquidation_distance_pct(mark_price, liq_price, side)
    is_liq = should_trigger_liquidation(mark_price, liq_price, side)

    return LiquidationEstimate(
        entry_price=entry_price,
        mark_price=mark_price,
        liquidation_price=liq_price,
        side=side,
        leverage=leverage,
        margin_mode=margin_mode,
        maintenance_margin_rate=maintenance_margin_rate,
        distance_pct=distance,
        is_liquidated=is_liq,
    )
