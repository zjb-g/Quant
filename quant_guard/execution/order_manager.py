"""quant_guard.execution.order_manager: 订单数据模型。

定义 OrderRequest / OrderResult / OrderStatus / OrderSide / OrderType。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    """订单方向。"""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型。"""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """订单状态。"""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class OrderRequest:
    """下单请求。

    所有字段在 ExecutionEngine.submit_order() 中构造，
    交给 RiskManager.check_order() 检查后才提交到交易所。
    """

    symbol: str
    side: OrderSide
    amount: float  # 合约数量
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None  # limit 单需要
    reduce_only: bool = False
    post_only: bool = False
    leverage: int = 5
    client_order_id: str = ""
    # 风控用附加字段
    notional: float = 0.0  # 名义价值（USDT），由 amount * price 计算
    strategy_id: str = ""
    signal_id: str = ""

    def __post_init__(self) -> None:
        # 如果未设 notional 且有 price，自动计算
        if self.notional == 0.0 and self.price is not None and self.price > 0:
            self.notional = self.amount * self.price

    def to_risk_check_dict(self) -> dict:
        """转为 RiskManager.check_order() 所需的字典格式。"""
        is_short = self.side == OrderSide.SELL
        return {
            "symbol": self.symbol,
            "side": "short" if is_short and not self.reduce_only else "long",
            "notional": self.notional,
            "leverage": self.leverage,
            "is_reduce_only": self.reduce_only,
        }


@dataclass
class OrderResult:
    """下单结果。"""

    client_order_id: str
    exchange_order_id: Optional[str]
    status: OrderStatus
    symbol: str
    side: OrderSide
    amount: float
    filled_amount: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    error: Optional[str] = None
    timestamp: int = 0

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_failed(self) -> bool:
        return self.status in (
            OrderStatus.REJECTED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
        )
