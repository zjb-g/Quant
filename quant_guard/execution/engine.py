"""quant_guard.execution.engine: 受风控约束的订单执行引擎。

所有下单必须先经过 RiskManager.check_order()，风控通过后才调用交易所。
默认 dry_run=True，不真实下单。live 模式必须显式确认。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from quant_guard.execution.idempotency import IdempotencyManager
from quant_guard.execution.order_manager import (
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
)
from quant_guard.risk.manager import RiskManager
from quant_guard.risk.rules import DecisionAction

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """订单执行引擎。

    所有订单必须经过 RiskManager 检查。

    参数：
        risk_manager: 风控管理器
        exchange_client: 交易所客户端（OKXClient 或 mock）
        dry_run: True 时只模拟不下单（默认 True）
        live_confirmed: True 时允许真实下单（需显式设置）
        idempotency: 幂等管理器
    """

    def __init__(
        self,
        risk_manager: RiskManager,
        exchange_client=None,
        dry_run: bool = True,
        live_confirmed: bool = False,
        idempotency: Optional[IdempotencyManager] = None,
    ) -> None:
        self.risk_manager = risk_manager
        self.exchange = exchange_client
        self.dry_run = dry_run
        self.live_confirmed = live_confirmed
        self.idempotency = idempotency or IdempotencyManager()

    def submit_order(
        self,
        order: OrderRequest,
        account_state: dict,
        market_state: dict,
    ) -> OrderResult:
        """提交订单。

        流程：
        1. 生成/检查幂等 client_order_id
        2. RiskManager 风控检查
        3. dry_run 模式模拟，live 模式真实下单

        参数：
            order: 订单请求
            account_state: 账户状态（供风控检查）
            market_state: 市场状态（供风控检查）

        返回：
            OrderResult
        """
        # 1. 幂等检查
        if not order.client_order_id:
            order.client_order_id = IdempotencyManager.generate_client_order_id(
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side.value,
                signal_id=order.signal_id,
            )
        # 1. 幂等检查（原子操作：check + mark 在同一调用中，避免并发窗口）
        if not self.idempotency.check_and_mark(order.client_order_id):
            logger.warning("duplicate order skipped: %s", order.client_order_id)
            return OrderResult(
                client_order_id=order.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                error="duplicate client_order_id",
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            )

        # 2. 风控检查
        risk_input = order.to_risk_check_dict()
        decision = self.risk_manager.check_order(order_request=risk_input, account_state=account_state, market_state=market_state)

        if not decision.allowed:
            logger.warning("order rejected by risk: %s (%s)", decision.reason, decision.rule_id)
            return OrderResult(
                client_order_id=order.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                error=f"risk rejected: {decision.reason}",
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            )

        # reduce_only 的特殊处理
        if decision.action == DecisionAction.REDUCE_ONLY and not order.reduce_only:
            order.reduce_only = True

        # 3. 执行
        if self.dry_run:
            return self._dry_run_order(order)
        elif not self.live_confirmed:
            logger.error("live mode not confirmed, refusing to submit")
            return OrderResult(
                client_order_id=order.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                error="live mode not confirmed",
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            )
        else:
            return self._live_order(order)

    def _dry_run_order(self, order: OrderRequest) -> OrderResult:
        """模拟下单（dry-run）。"""
        logger.info("dry-run order: %s %s %s", order.symbol, order.side.value, order.amount)
        return OrderResult(
            client_order_id=order.client_order_id,
            exchange_order_id=f"dry_{order.client_order_id[:8]}",
            status=OrderStatus.FILLED,
            symbol=order.symbol,
            side=order.side,
            amount=order.amount,
            filled_amount=order.amount,
            avg_price=order.price or 0.0,
            fee=0.0,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
        )

    def _live_order(self, order: OrderRequest) -> OrderResult:
        """真实下单（需要 exchange_client）。"""
        if self.exchange is None:
            raise RuntimeError("exchange client not configured for live mode")

        self.idempotency.mark_submitted(order.client_order_id)  # 已经由 check_and_mark 标记，此处保留作为安全网
        logger.info("live order: %s %s %s", order.symbol, order.side.value, order.amount)

        try:
            from quant_guard.exchange.models import Side

            if order.reduce_only:
                pos_side = Side.LONG if order.side == OrderSide.SELL else Side.SHORT
                raw = self.exchange.create_reduce_only_market_order(
                    order.symbol, pos_side, order.amount
                )
            else:
                raise RuntimeError("non reduce-only live orders not implemented yet")

            return OrderResult(
                client_order_id=order.client_order_id,
                exchange_order_id=str(raw.get("id", "")),
                status=OrderStatus.FILLED,
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                filled_amount=float(raw.get("filled", order.amount) or order.amount),
                avg_price=float(raw.get("average", order.price or 0) or 0),
                fee=float((raw.get("fee") or {}).get("cost", 0) or 0),
                timestamp=int(raw.get("timestamp", 0) or 0),
            )
        except Exception as exc:
            logger.exception("live order failed: %s", exc)
            return OrderResult(
                client_order_id=order.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                error=str(exc),
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            )

    def sync_state_from_exchange(self) -> dict:
        """重启后从交易所同步状态（T4.4）。

        查询 open orders / positions / account balance，
        本地状态以交易所返回为准。

        返回：
            同步后的状态字典
        """
        if self.exchange is None:
            logger.warning("no exchange client, skip sync")
            return {}

        # TODO: 接入真实同步逻辑
        # positions = self.exchange.get_positions()
        # balance = self.exchange.get_balance()
        # open_orders = self.exchange.get_open_orders()
        # 对账本地状态，不一致时记录告警

        logger.info("state sync from exchange (placeholder)")
        return {"synced": True, "positions": 0, "open_orders": 0}
