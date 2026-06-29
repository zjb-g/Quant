"""quant_guard.risk.state: 风控状态管理。

记录权益高水位、当前权益、日初权益、回撤、每日亏损等状态。
T3.4 最大回撤熔断与每日亏损限额依赖此模块。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RiskState:
    """风控状态。

    由 RiskManager 维护，每次下单前检查。
    """

    # 权益追踪
    equity_high_watermark: float = 1000.0  # 权益历史最高值
    current_equity: float = 1000.0  # 当前权益
    daily_start_equity: float = 1000.0  # 当日开盘权益
    daily_realized_pnl: float = 0.0  # 当日已实现盈亏

    # Kill switch
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_activated_at: Optional[str] = None

    # 日期追踪
    current_date: Optional[str] = None  # YYYY-MM-DD，用于检测跨日重置

    def update_equity(self, equity: float) -> None:
        """更新当前权益，自动更新高水位。"""
        self.current_equity = equity
        if equity > self.equity_high_watermark:
            self.equity_high_watermark = equity

    def record_realized_pnl(self, pnl: float) -> None:
        """记录一笔已实现盈亏。"""
        self.daily_realized_pnl += pnl
        # 已实现盈亏影响当前权益
        self.update_equity(self.current_equity + pnl)

    def check_daily_reset(self, now: Optional[datetime] = None) -> bool:
        """检查是否跨日，跨日则重置每日统计。

        返回 True 表示发生了跨日重置。
        """
        if now is None:
            now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        if self.current_date is None:
            self.current_date = today
            self.daily_start_equity = self.current_equity
            self.daily_realized_pnl = 0.0
            return True

        if self.current_date != today:
            # 跨日重置
            self.current_date = today
            self.daily_start_equity = self.current_equity
            self.daily_realized_pnl = 0.0
            return True

        return False

    @property
    def current_drawdown_pct(self) -> float:
        """当前回撤百分比（相对高水位）。"""
        if self.equity_high_watermark <= 0:
            return 0.0
        dd = (self.equity_high_watermark - self.current_equity) / self.equity_high_watermark * 100.0
        return round(dd, 4)

    @property
    def daily_loss_pct(self) -> float:
        """当日亏损百分比（相对日初权益，正数=亏损）。"""
        if self.daily_start_equity <= 0:
            return 0.0
        loss = (self.daily_start_equity - self.current_equity) / self.daily_start_equity * 100.0
        return round(loss, 4)

    def activate_kill_switch(self, reason: str, now: Optional[datetime] = None) -> None:
        """激活 kill switch。"""
        if now is None:
            now = datetime.now(timezone.utc)
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self.kill_switch_activated_at = now.isoformat()

    def deactivate_kill_switch(self) -> None:
        """解除 kill switch（谨慎操作）。"""
        self.kill_switch_active = False
        self.kill_switch_reason = None
        self.kill_switch_activated_at = None

    def to_dict(self) -> dict:
        """转为字典（供 API 序列化）。"""
        return {
            "kill_switch": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "equity_high_watermark": self.equity_high_watermark,
            "current_equity": self.current_equity,
            "current_drawdown_pct": self.current_drawdown_pct,
            "daily_start_equity": self.daily_start_equity,
            "daily_loss_pct": self.daily_loss_pct,
            "daily_realized_pnl": self.daily_realized_pnl,
        }
