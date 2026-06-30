"""quant_guard.services.control_service: 统一风控 + 执行 + 紧急处置。

Web 控制台 Kill Switch / 紧急全平 / Bot 启停均经此模块，
确保 RiskManager 与 Freqtrade 进程状态一致。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from quant_guard.execution.engine import ExecutionEngine
from quant_guard.execution.order_manager import OrderRequest, OrderResult, OrderSide, OrderType
from quant_guard.exchange.models import Side
from quant_guard.risk.manager import RiskManager
from quant_guard.risk.rules import RiskConfig as RulesRiskConfig

logger = logging.getLogger(__name__)

AlertCallback = Callable[[str, str, str], None]


@dataclass
class ControlService:
    """系统控制与风控单例。"""

    risk_manager: RiskManager = field(default_factory=RiskManager)
    _alert_callback: Optional[AlertCallback] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.risk_manager.add_alert_callback(self._on_risk_alert)

    def set_alert_callback(self, callback: AlertCallback) -> None:
        self._alert_callback = callback

    def _on_risk_alert(self, level: str, alert_type: str, message: str) -> None:
        if self._alert_callback:
            self._alert_callback(level, alert_type, message)

    def update_config(self, config: dict) -> None:
        """同步 API 风控配置到 RiskManager。"""
        self.risk_manager.update_config(RulesRiskConfig(**config))

    def get_api_risk_state(self) -> dict:
        """返回供 FastAPI RiskState 模型使用的字典。"""
        raw = self.risk_manager.get_state_dict()
        return {
            "kill_switch": raw.get("kill_switch", False),
            "kill_switch_reason": raw.get("kill_switch_reason"),
            "max_leverage": raw.get("max_leverage", 5),
            "max_total_notional": raw.get("max_total_notional", 1000.0),
            "current_total_notional": 0.0,
            "equity_high_watermark": raw.get("equity_high_watermark", 1000.0),
            "current_equity": raw.get("current_equity", 1000.0),
            "max_drawdown_pct": raw.get("current_drawdown_pct", 0.0),
            "daily_start_equity": raw.get("daily_start_equity", 1000.0),
            "daily_loss_pct": raw.get("daily_loss_pct", 0.0),
            "daily_loss_limit_pct": self.risk_manager.config.daily_loss_stop_pct,
        }

    def is_kill_switch_active(self) -> bool:
        return self.risk_manager.is_kill_switch_active

    def activate_kill_switch(self, reason: str) -> dict:
        """激活 Kill Switch 并停止 Freqtrade Bot。"""
        from quant_guard.services.freqtrade_service import freqtrade_service

        self.risk_manager.activate_kill_switch(reason)
        bot = freqtrade_service.stop_bot()
        logger.critical("kill switch activated: %s", reason)
        return {
            "status": "kill_switch_activated",
            "reason": reason,
            "bot_stopped": not bot.running,
        }

    def deactivate_kill_switch(self) -> dict:
        """解除 Kill Switch（谨慎操作）。"""
        self.risk_manager.deactivate_kill_switch()
        return {"status": "kill_switch_deactivated"}

    def _build_execution_engine(self, *, dry_run: bool, live_confirmed: bool) -> ExecutionEngine:
        from quant_guard.exchange.okx_client import OKXClient, OKXClientError

        client = None
        if not dry_run or live_confirmed:
            try:
                client = OKXClient(public_only=False)
            except OKXClientError as exc:
                if not dry_run:
                    raise RuntimeError(str(exc)) from exc
        return ExecutionEngine(
            risk_manager=self.risk_manager,
            exchange_client=client,
            dry_run=dry_run,
            live_confirmed=live_confirmed,
        )

    def _account_state_from_positions(self, positions) -> dict:
        symbol_notionals: dict[str, float] = {}
        total = 0.0
        for p in positions:
            notional = abs(p.contracts * p.mark_price)
            symbol_notionals[p.symbol] = symbol_notionals.get(p.symbol, 0.0) + notional
            total += notional
        return {
            "current_total_notional": total,
            "symbol_notionals": symbol_notionals,
        }

    def emergency_close_all(self, *, reason: str = "emergency_close") -> dict:
        """紧急全平：停 Bot → Kill Switch → 对所有持仓发 reduce-only 市价单。"""
        from quant_guard.exchange.okx_client import OKXClient, OKXClientError
        from quant_guard.services.freqtrade_service import freqtrade_service

        self.activate_kill_switch(reason)
        freqtrade_service.stop_bot()

        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        dry_run = not live_confirmed

        try:
            client = OKXClient(public_only=False)
            positions = client.get_positions()
        except OKXClientError as exc:
            return {
                "status": "emergency_close_skipped",
                "reason": reason,
                "dry_run": True,
                "closed": 0,
                "message": f"无法连接 OKX: {exc}",
                "results": [],
            }

        if not positions:
            return {
                "status": "emergency_close_done",
                "reason": reason,
                "dry_run": dry_run,
                "closed": 0,
                "message": "无持仓",
                "results": [],
            }

        engine = self._build_execution_engine(dry_run=dry_run, live_confirmed=live_confirmed)
        account_state = self._account_state_from_positions(positions)
        market_state = {"liquidation_distance_pct": 100.0}
        results: list[dict] = []

        for pos in positions:
            side = OrderSide.SELL if pos.side == Side.LONG else OrderSide.BUY
            notional = abs(pos.contracts * (pos.mark_price or pos.entry_price or 0))
            order = OrderRequest(
                symbol=pos.symbol,
                side=side,
                amount=abs(pos.contracts),
                order_type=OrderType.MARKET,
                price=pos.mark_price or pos.entry_price,
                reduce_only=True,
                leverage=int(pos.leverage or 1),
                notional=notional,
                strategy_id="emergency_close",
                signal_id=f"close_{pos.symbol}",
            )
            result: OrderResult = engine.submit_order(order, account_state, market_state)
            results.append({
                "symbol": result.symbol,
                "status": result.status.value,
                "error": result.error,
                "exchange_order_id": result.exchange_order_id,
            })

        filled = sum(1 for r in results if r.get("status") == "filled")
        return {
            "status": "emergency_close_executed",
            "reason": reason,
            "dry_run": dry_run,
            "closed": filled,
            "attempted": len(results),
            "results": results,
        }


control_service = ControlService()
