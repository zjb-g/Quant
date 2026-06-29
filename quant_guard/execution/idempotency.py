"""quant_guard.execution.idempotency: clientOrderId 幂等模块。

根据 strategy_id、symbol、side、timestamp_bucket、signal_id 生成 client_order_id。
本地记录已提交订单 ID，重试时如果 ID 已存在，不重复提交。
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class IdempotencyManager:
    """clientOrderId 幂等管理器。

    防止网络抖动导致重复下单。
    """

    _submitted_ids: Set[str] = field(default_factory=set)

    @staticmethod
    def generate_client_order_id(
        strategy_id: str,
        symbol: str,
        side: str,
        signal_id: str = "",
        timestamp_bucket: Optional[int] = None,
    ) -> str:
        """生成幂等的 client_order_id。

        相同输入（同一信号同一时间桶）生成相同 ID，
        确保重试时不重复下单。

        参数：
            strategy_id: 策略标识
            symbol: 交易对
            side: 买卖方向
            signal_id: 信号标识（可选）
            timestamp_bucket: 时间桶（秒，默认当前 5 秒桶）

        返回：
            32 字符 hex 字符串
        """
        if timestamp_bucket is None:
            # 5 秒时间桶：同一信号 5 秒内重试生成相同 ID
            timestamp_bucket = int(time.time()) // 5

        raw = f"{strategy_id}|{symbol}|{side}|{signal_id}|{timestamp_bucket}"
        return hashlib.md5(raw.encode()).hexdigest()

    def is_submitted(self, client_order_id: str) -> bool:
        """检查该 client_order_id 是否已提交过。"""
        return client_order_id in self._submitted_ids

    def mark_submitted(self, client_order_id: str) -> None:
        """标记 client_order_id 为已提交。"""
        self._submitted_ids.add(client_order_id)

    def check_and_mark(self, client_order_id: str) -> bool:
        """检查并标记。返回 True 表示首次（可提交），False 表示重复。"""
        if client_order_id in self._submitted_ids:
            return False
        self._submitted_ids.add(client_order_id)
        return True

    def clear(self) -> None:
        """清空已提交记录（谨慎操作）。"""
        self._submitted_ids.clear()

    @property
    def count(self) -> int:
        """已提交订单数。"""
        return len(self._submitted_ids)
