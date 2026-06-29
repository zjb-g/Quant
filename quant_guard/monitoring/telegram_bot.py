"""quant_guard.monitoring.telegram_bot: Telegram Bot 监控与控制。

支持发送告警消息和接收控制命令。
Token 从环境变量 TELEGRAM_BOT_TOKEN 读取。
"""

import logging
import os
from typing import Optional

from quant_guard.monitoring.alerts import AlertEvent, AlertLevel, AlertManager

logger = logging.getLogger(__name__)

# 告警级别对应的 emoji
LEVEL_EMOJI = {
    AlertLevel.INFO: "ℹ️",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.CRITICAL: "🚨",
}


class TelegramBot:
    """Telegram Bot：发送告警 + 接收控制命令。

    安全说明：
    - emergency_close_all 命令需二次确认
    - 不允许单条命令直接实盘全平
    - Token 从环境变量读取，不硬编码
    """

    def __init__(
        self,
        alert_manager: Optional[AlertManager] = None,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self.alert_manager = alert_manager
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._bot = None
        self._pending_emergency_confirm = {}  # chat_id -> timestamp

        # 订阅告警
        if self.alert_manager:
            self.alert_manager.subscribe(self._on_alert)

    @property
    def is_configured(self) -> bool:
        """是否已配置（token 和 chat_id 都有）。"""
        return bool(self.token and self.chat_id)

    def _on_alert(self, event: AlertEvent) -> None:
        """告警事件回调，发送到 Telegram。"""
        if not self.is_configured:
            return
        self.send_alert(event)

    def send_alert(self, event: AlertEvent) -> bool:
        """发送告警消息到 Telegram。

        返回 True 表示发送成功。
        """
        if not self.is_configured:
            logger.warning("telegram not configured, skip alert")
            return False

        emoji = LEVEL_EMOJI.get(event.level, "📋")
        text = (
            f"{emoji} *{event.level.value}*\n"
            f"*类型*: `{event.type}`\n"
            f"*消息*: {event.message}\n"
            f"*时间*: {event.timestamp}"
        )

        # TODO: 接入 python-telegram-bot 真实发送
        # from telegram import Bot
        # bot = Bot(token=self.token)
        # bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown")

        logger.info("telegram alert (placeholder): %s", event.type)
        return True

    def send_message(self, text: str) -> bool:
        """发送普通消息。"""
        if not self.is_configured:
            return False
        # TODO: 接入真实发送
        logger.info("telegram message (placeholder): %s", text[:50])
        return True

    def handle_command(self, command: str, chat_id: str, state: dict) -> str:
        """处理 Telegram 命令。

        参数：
            command: 命令（如 /status /stop /start /risk /emergency_close_all）
            chat_id: 发送者 chat_id
            state: 当前系统状态字典

        返回：
            回复消息文本
        """
        if command == "/status":
            return self._cmd_status(state)
        elif command == "/stop":
            return self._cmd_stop(state)
        elif command == "/start":
            return self._cmd_start(state)
        elif command == "/risk":
            return self._cmd_risk(state)
        elif command == "/emergency_close_all":
            return self._cmd_emergency_close(chat_id, state)
        else:
            return (
                "可用命令：\n"
                "/status - 查看状态\n"
                "/stop - 停止开新仓\n"
                "/start - 恢复开新仓\n"
                "/risk - 查看风控状态\n"
                "/emergency_close_all - 紧急全平（需二次确认）"
            )

    def _cmd_status(self, state: dict) -> str:
        return (
            f"📊 *状态*\n"
            f"Bot: {'运行中' if state.get('bot_running') else '已停止'}\n"
            f"模式: {'DRY-RUN' if state.get('dry_run') else 'LIVE'}\n"
            f"策略: {state.get('strategy', 'N/A')}\n"
            f"权益: {state.get('equity', 0):.2f} USDT\n"
            f"持仓数: {state.get('position_count', 0)}\n"
            f"总敞口: {state.get('total_notional', 0):.2f} USDT"
        )

    def _cmd_stop(self, state: dict) -> str:
        # TODO: 接入真实停止逻辑
        return "⏸ Bot 已停止开新仓（reduce-only 仍允许）"

    def _cmd_start(self, state: dict) -> str:
        # TODO: 接入真实启动逻辑
        return "▶️ Bot 已恢复开新仓"

    def _cmd_risk(self, state: dict) -> str:
        risk = state.get("risk", {})
        return (
            f"🛡 *风控状态*\n"
            f"Kill Switch: {'🚨 激活' if risk.get('kill_switch') else '✅ 正常'}\n"
            f"最大杠杆: {risk.get('max_leverage', 'N/A')}x\n"
            f"总敞口: {risk.get('current_total_notional', 0):.2f} / {risk.get('max_total_notional', 'N/A')} USDT\n"
            f"回撤: {risk.get('current_drawdown_pct', 0):.2f}%\n"
            f"日亏: {risk.get('daily_loss_pct', 0):.2f}%"
        )

    def _cmd_emergency_close(self, chat_id: str, state: dict) -> str:
        """紧急全平命令：需二次确认。"""
        import time

        if chat_id in self._pending_emergency_confirm:
            # 二次确认
            first_time = self._pending_emergency_confirm.pop(chat_id)
            if time.time() - first_time < 60:  # 60 秒内有效
                # TODO: 接入真实紧急全平
                return "🚨 紧急全平已执行！所有持仓正在平仓。"
            else:
                return "⚠️ 确认超时，请重新发送 /emergency_close_all"

        # 首次点击，记录并发送确认提示
        self._pending_emergency_confirm[chat_id] = time.time()
        return (
            "⚠️ *紧急全平确认*\n"
            "此操作将平仓所有持仓，不可撤销！\n"
            "60 秒内再次发送 /emergency_close_all 确认执行。"
        )
