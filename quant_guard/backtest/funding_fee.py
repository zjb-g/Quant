"""quant_guard.backtest.funding_fee: 资金费计算模块。

用于回测报告与实盘 PnL 统计中的资金费成本计算。
OKX 永续合约每 8h 结算一次（00/08/16 UTC），ADR-006。

资金费方向规则：
- funding_rate > 0：多头付给空头（多头成本，空头收益）
- funding_rate < 0：空头付给多头（空头成本，多头收益）

费用 = position_notional * funding_rate * direction_sign
  - long:  direction_sign = +1（费率为正时多头付费）
  - short: direction_sign = -1（费率为正时空头收费）
"""

from dataclasses import dataclass, field
from typing import List

from quant_guard.exchange.models import Side


@dataclass(frozen=True)
class FundingFeeEntry:
    """单次资金费结算记录。"""

    timestamp: int  # 结算时间戳（毫秒）
    position_notional: float  # 持仓名义价值
    funding_rate: float  # 资金费率
    side: Side  # 持仓方向
    fee: float  # 资金费（正=成本支出，负=收益收入）


@dataclass
class FundingFeeSummary:
    """资金费汇总。"""

    entries: List[FundingFeeEntry] = field(default_factory=list)

    @property
    def total_fee(self) -> float:
        """累计资金费（正=总成本，负=总收益）。"""
        return sum(e.fee for e in self.entries)

    @property
    def count(self) -> int:
        """结算次数。"""
        return len(self.entries)


def calculate_funding_fee(
    position_notional: float,
    funding_rate: float,
    side: Side,
    timestamp: int = 0,
) -> FundingFeeEntry:
    """计算单次资金费。

    参数：
        position_notional: 持仓名义价值（USDT）
        funding_rate: 资金费率（如 0.0001 = 0.01%）
        side: 持仓方向（long/short）
        timestamp: 结算时间戳（毫秒，可选）

    返回：
        FundingFeeEntry，fee 字段为实际费用：
        - 正数 = 成本支出（你付钱）
        - 负数 = 收益收入（你收钱）

    示例：
        # 多头持仓 1000 USDT，费率 0.01%
        >>> calculate_funding_fee(1000, 0.0001, Side.LONG).fee
        0.1  # 多头支付 0.1 USDT

        # 空头持仓 1000 USDT，费率 0.01%
        >>> calculate_funding_fee(1000, 0.0001, Side.SHORT).fee
        -0.1  # 空头收取 0.1 USDT
    """
    if position_notional < 0:
        raise ValueError("position_notional must be non-negative")

    # 方向符号：多头费率为正时付费（+1），空头费率为正时收费（-1）
    direction_sign = 1.0 if side == Side.LONG else -1.0
    fee = position_notional * funding_rate * direction_sign

    return FundingFeeEntry(
        timestamp=timestamp,
        position_notional=position_notional,
        funding_rate=funding_rate,
        side=side,
        fee=fee,
    )


def accumulate_funding_fees(
    entries: List[FundingFeeEntry],
) -> FundingFeeSummary:
    """累加多次资金费结算，返回汇总。

    参数：
        entries: 多次资金费结算记录列表

    返回：
        FundingFeeSummary，含 total_fee 和 count
    """
    return FundingFeeSummary(entries=list(entries))


def calculate_funding_fee_series(
    position_notional: float,
    funding_rates: List[float],
    side: Side,
    timestamps: List[int] = None,
) -> FundingFeeSummary:
    """批量计算多个周期的资金费。

    参数：
        position_notional: 持仓名义价值（假设不变）
        funding_rates: 各周期资金费率列表
        side: 持仓方向
        timestamps: 各周期结算时间戳列表（可选，默认全 0）

    返回：
        FundingFeeSummary
    """
    if timestamps is None:
        timestamps = [0] * len(funding_rates)
    if len(timestamps) != len(funding_rates):
        raise ValueError("timestamps length must match funding_rates length")

    entries = [
        calculate_funding_fee(position_notional, rate, side, ts)
        for rate, ts in zip(funding_rates, timestamps)
    ]
    return accumulate_funding_fees(entries)
