"""quant_guard.services.exchange_service: 交易所数据服务。

连接交易所（OKX/gate），获取真实持仓、余额、历史交易数据。
API Key 从环境变量读取，不硬编码。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import ccxt


def _load_dotenv() -> None:
    """加载 .env（若存在）。"""
    env_path = Path(".env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            pass


@dataclass
class ExchangeConnection:
    """交易所连接状态。"""

    connected: bool
    exchange: str
    error: str = ""
    account_mode: str = ""


@dataclass
class AccountBalance:
    """账户余额。"""

    total: float
    free: float
    used: float
    currency: str


@dataclass
class HistoricalTrade:
    """历史交易记录。"""

    id: str
    timestamp: str
    symbol: str
    side: str  # buy / sell
    amount: float
    price: float
    fee: float
    pnl: float


@dataclass
class HistoricalPosition:
    """历史持仓（已平仓）。"""

    position_id: str
    symbol: str
    side: str
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
    close_type: str
    open_time: str
    close_time: str


class ExchangeService:
    """交易所数据服务。

    从环境变量读取 API Key 连接交易所。
    支持查询：连接状态、余额、持仓、历史交易。
    """

    def __init__(self) -> None:
        self._exchange: Optional[ccxt.Exchange] = None
        self._exchange_name = ""

    def _get_exchange(self) -> ccxt.Exchange:
        """获取或创建交易所连接。"""
        if self._exchange is not None:
            return self._exchange

        _load_dotenv()
        for name in ["okx", "gate"]:
            api_key = os.environ.get(f"{name.upper()}_API_KEY", "")
            api_secret = os.environ.get(f"{name.upper()}_API_SECRET", "")
            passphrase = os.environ.get(f"{name.upper()}_API_PASSPHRASE", "")

            # OKX 需要 passphrase，gate 不需要
            if name == "okx" and not all([api_key, api_secret, passphrase]):
                continue
            if name == "gate" and not all([api_key, api_secret]):
                continue

            try:
                exchange_class = getattr(ccxt, name)
                config = {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "timeout": 15000,
                    "options": {"defaultType": "swap"},
                }
                if name == "okx":
                    config["password"] = passphrase

                self._exchange = exchange_class(config)
                self._exchange_name = name
                return self._exchange
            except Exception:
                continue

        raise RuntimeError("无可用的交易所连接。请配置 OKX_API_KEY 或 GATE_API_KEY 环境变量。")

    def test_connection(self) -> ExchangeConnection:
        """测试交易所连接。"""
        try:
            ex = self._get_exchange()
            # 尝试获取余额验证连接
            balance = ex.fetch_balance()
            return ExchangeConnection(
                connected=True,
                exchange=self._exchange_name,
                account_mode="unified" if self._exchange_name == "okx" else "standard",
            )
        except RuntimeError as e:
            return ExchangeConnection(connected=False, exchange="", error=str(e))
        except Exception as e:
            return ExchangeConnection(
                connected=False,
                exchange=self._exchange_name,
                error=f"连接失败: {type(e).__name__}: {str(e)[:100]}",
            )

    def get_balance(self) -> AccountBalance:
        """获取账户余额。"""
        ex = self._get_exchange()
        raw = ex.fetch_balance()
        total = raw.get("total", {})
        free = raw.get("free", {})
        used = raw.get("used", {})

        # 优先 USDT
        currency = "USDT"
        if currency not in total:
            currency = list(total.keys())[0] if total else "USDT"

        return AccountBalance(
            total=float(total.get(currency, 0)),
            free=float(free.get(currency, 0)),
            used=float(used.get(currency, 0)),
            currency=currency,
        )

    def get_positions(self) -> List[dict]:
        """获取当前持仓。"""
        ex = self._get_exchange()
        try:
            raw_positions = ex.fetch_positions()
        except Exception as e:
            raise RuntimeError(f"获取持仓失败: {e}") from e

        positions = []
        for p in raw_positions:
            contracts = float(p.get("contracts", 0) or 0)
            if contracts == 0:
                continue  # 跳过空仓
            positions.append({
                "symbol": p.get("symbol", ""),
                "side": p.get("side", ""),
                "contracts": contracts,
                "entry_price": float(p.get("entryPrice", 0) or 0),
                "mark_price": float(p.get("markPrice", 0) or 0),
                "leverage": float(p.get("leverage", 1) or 1),
                "unrealized_pnl": float(p.get("unrealizedPnl", 0) or 0),
                "liquidation_price": float(p.get("liquidationPrice", 0)) if p.get("liquidationPrice") else None,
                "margin_mode": p.get("marginMode", ""),
                "notional": float(p.get("notional", 0) or 0),
                "percentage": float(p.get("percentage", 0) or 0),
            })
        return positions

    def get_positions_history(
        self, limit: int = 100, fetch_all: bool = False
    ) -> List[HistoricalPosition]:
        """获取历史持仓（已平仓记录）。当前仅支持 OKX。"""
        self._get_exchange()
        if self._exchange_name != "okx":
            raise RuntimeError("历史持仓查询仅支持 OKX 交易所")

        from datetime import datetime, timezone

        from quant_guard.exchange.okx_client import OKXClient

        client = OKXClient(public_only=False)
        raw = client.get_positions_history(limit=limit, fetch_all=fetch_all)

        def _fmt_ts(ms: int) -> str:
            if not ms:
                return ""
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

        return [
            HistoricalPosition(
                position_id=h.position_id,
                symbol=h.symbol,
                side=h.side.value,
                leverage=h.leverage,
                margin_mode=h.margin_mode,
                open_avg_price=h.open_avg_price,
                close_avg_price=h.close_avg_price,
                close_size=h.close_size,
                pnl=h.pnl,
                realized_pnl=h.realized_pnl,
                pnl_ratio=h.pnl_ratio,
                fee=h.fee,
                funding_fee=h.funding_fee,
                close_type=h.close_type.value,
                open_time=_fmt_ts(h.open_time),
                close_time=_fmt_ts(h.close_time),
            )
            for h in raw
        ]

    def get_historical_trades(self, limit: int = 100) -> List[HistoricalTrade]:
        """获取历史交易记录。"""
        ex = self._get_exchange()
        try:
            raw_trades = ex.fetch_my_trades(limit=limit)
        except Exception as e:
            raise RuntimeError(f"获取历史交易失败: {e}") from e

        from datetime import datetime, timezone
        trades = []
        for t in raw_trades:
            ts = t.get("timestamp", 0)
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else ""
            trades.append(HistoricalTrade(
                id=t.get("id", ""),
                timestamp=dt,
                symbol=t.get("symbol", ""),
                side=t.get("side", ""),
                amount=float(t.get("amount", 0) or 0),
                price=float(t.get("price", 0) or 0),
                fee=float(t.get("fee", {}).get("cost", 0) or 0),
                pnl=0,  # ccxt my_trades 不直接返回 pnl，需从 closed orders 获取
            ))
        return trades

    def get_open_orders(self) -> List[dict]:
        """获取当前挂单。"""
        ex = self._get_exchange()
        try:
            raw = ex.fetch_open_orders()
        except Exception as e:
            raise RuntimeError(f"获取挂单失败: {e}") from e

        from datetime import datetime, timezone
        orders = []
        for o in raw:
            ts = o.get("timestamp", 0)
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else ""
            orders.append({
                "id": o.get("id", ""),
                "timestamp": dt,
                "symbol": o.get("symbol", ""),
                "type": o.get("type", ""),
                "side": o.get("side", ""),
                "amount": float(o.get("amount", 0) or 0),
                "price": float(o.get("price", 0) or 0),
                "filled": float(o.get("filled", 0) or 0),
                "remaining": float(o.get("remaining", 0) or 0),
                "status": o.get("status", ""),
            })
        return orders
