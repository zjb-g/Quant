"""quant_guard.monitoring.alerts: 告警事件模型。

定义 AlertEvent 和告警级别，供 Telegram Bot 和 Web UI 使用。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class AlertLevel(str, Enum):
    """告警级别。"""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType:
    """告警事件类型常量。"""

    ORDER_SUBMITTED = "order_submitted"
    ORDER_REJECTED = "order_rejected"
    RISK_TRIGGERED = "risk_triggered"
    LIQUIDATION_WARNING = "liquidation_warning"
    API_ERROR = "api_error"
    HEARTBEAT_MISSED = "heartbeat_missed"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    STATE_MISMATCH = "state_mismatch"


@dataclass
class AlertEvent:
    """告警事件。"""

    level: AlertLevel
    type: str
    message: str
    timestamp: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.id:
            self.id = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level.value,
            "type": self.type,
            "message": self.message,
        }


class AlertManager:
    """告警管理器：收集告警事件，通知订阅者。"""

    def __init__(self, max_size: int = 500) -> None:
        self._alerts: List[AlertEvent] = []
        self._max_size = max_size
        self._subscribers: List = []

    def emit(self, level: AlertLevel, alert_type: str, message: str) -> AlertEvent:
        """发出告警事件。"""
        event = AlertEvent(level=level, type=alert_type, message=message)
        self._alerts.insert(0, event)
        if len(self._alerts) > self._max_size:
            self._alerts = self._alerts[: self._max_size]
        # 通知订阅者
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                pass
        return event

    def get_alerts(self, limit: int = 100, level: Optional[AlertLevel] = None) -> List[AlertEvent]:
        """获取告警列表。"""
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts[:limit]

    def subscribe(self, callback) -> None:
        """订阅告警事件。"""
        self._subscribers.append(callback)

    @property
    def critical_count(self) -> int:
        """CRITICAL 级别告警数。"""
        return sum(1 for a in self._alerts if a.level == AlertLevel.CRITICAL)

    @property
    def warning_count(self) -> int:
        """WARNING 级别告警数。"""
        return sum(1 for a in self._alerts if a.level == AlertLevel.WARNING)
