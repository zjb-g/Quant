"""quant_guard.exchange.models: 交易所数据模型。

定义 OKX 行情与账户相关的标准数据结构，供 okx_client 与上层模块使用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Side(str, Enum):
    """持仓方向。"""

    LONG = "long"
    SHORT = "short"


class CloseType(str, Enum):
    """历史持仓平仓类型（OKX positions-history type 字段）。"""

    PARTIAL = "partial"
    FULL = "full"
    LIQUIDATION = "liquidation"
    FORCED_REDUCTION = "forced_reduction"
    ADL = "adl"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Ticker:
    """最新行情快照。"""

    symbol: str
    last_price: float
    bid: float
    ask: float
    timestamp: int  # 毫秒


@dataclass(frozen=True)
class Ohlcv:
    """单根 K 线。"""

    symbol: str
    timeframe: str
    timestamp: int  # 毫秒
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class FundingRate:
    """资金费率。"""

    symbol: str
    funding_rate: float
    next_funding_time: int  # 毫秒
    timestamp: int  # 毫秒


@dataclass(frozen=True)
class MarkPrice:
    """标记价格。"""

    symbol: str
    mark_price: float
    timestamp: int  # 毫秒


@dataclass(frozen=True)
class Position:
    """账户持仓（仅私有模式可获取）。"""

    symbol: str
    side: Side
    contracts: float
    entry_price: float
    mark_price: float
    leverage: float
    unrealized_pnl: float
    liquidation_price: Optional[float] = None
    timestamp: int = 0


@dataclass(frozen=True)
class PositionHistory:
    """已平仓历史持仓（OKX positions-history）。"""

    position_id: str
    symbol: str
    side: Side
    leverage: float
    margin_mode: str
    open_avg_price: float
    close_avg_price: float
    close_size: float
    pnl: float
    realized_pnl: float
    pnl_ratio: float
    fee: float
    funding_fee: float
    close_type: CloseType
    open_time: int
    close_time: int
