"""quant_guard.monitoring.heartbeat: 进程心跳监控。

定时记录 bot alive 状态，超时触发 CRITICAL alert。
可被 Docker healthcheck 调用。
"""

import time
from datetime import datetime, timezone
from typing import Optional

from quant_guard.monitoring.alerts import AlertLevel, AlertManager, AlertType


class HeartbeatMonitor:
    """心跳监控器。

    用法：
        hb = HeartbeatMonitor(alert_manager, timeout=60)
        hb.beat()  # 定时调用（如每 10 秒）
        hb.check()  # 另一个定时器检查是否超时

    Docker healthcheck 可调用：
        python -c "from quant_guard.monitoring.heartbeat import check_health; check_health()"
    """

    def __init__(
        self,
        alert_manager: Optional[AlertManager] = None,
        timeout: int = 60,
        beat_interval: int = 10,
    ) -> None:
        self.alert_manager = alert_manager
        self.timeout = timeout
        self.beat_interval = beat_interval
        self._last_beat: float = time.time()
        self._started_at: float = time.time()

    def beat(self) -> None:
        """记录一次心跳。"""
        self._last_beat = time.time()

    @property
    def seconds_since_last_beat(self) -> float:
        """距上次心跳的秒数。"""
        return time.time() - self._last_beat

    @property
    def is_alive(self) -> bool:
        """是否存活（心跳未超时）。"""
        return self.seconds_since_last_beat < self.timeout

    @property
    def uptime_seconds(self) -> float:
        """运行时长（秒）。"""
        return time.time() - self._started_at

    def check(self) -> bool:
        """检查心跳是否超时，超时触发告警。

        返回 True 表示正常，False 表示超时。
        """
        if not self.is_alive:
            if self.alert_manager:
                self.alert_manager.emit(
                    AlertLevel.CRITICAL,
                    AlertType.HEARTBEAT_MISSED,
                    f"heartbeat missed: {self.seconds_since_last_beat:.0f}s > timeout {self.timeout}s",
                )
            return False
        return True

    def status(self) -> dict:
        """获取心跳状态（供 API）。"""
        return {
            "alive": self.is_alive,
            "seconds_since_last_beat": round(self.seconds_since_last_beat, 1),
            "timeout": self.timeout,
            "uptime_seconds": round(self.uptime_seconds, 0),
        }


def check_health(heartbeat_file: str = "user_data/logs/heartbeat.json") -> bool:
    """Docker healthcheck 调用的健康检查函数。

    检查心跳文件是否在超时时间内更新。
    返回 True 表示健康，False 表示不健康。
    """
    import json
    import os

    if not os.path.exists(heartbeat_file):
        return False

    try:
        with open(heartbeat_file, encoding="utf-8") as f:
            data = json.load(f)
        last_beat = data.get("timestamp", 0)
        timeout = data.get("timeout", 60)
        age = time.time() - last_beat
        return age < timeout
    except Exception:
        return False
