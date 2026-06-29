"""quant_guard.utils.live_guard: live 启动门禁（T7.2）。

dry_run=false 时必须检查环境变量，缺一拒绝启动 live。
"""

import os
from dataclasses import dataclass
from typing import List


@dataclass
class LiveGuardResult:
    """live_guard 检查结果。"""

    passed: bool
    missing: List[str]
    failures: List[str]

    @property
    def error_message(self) -> str:
        if self.passed:
            return ""
        parts = []
        if self.missing:
            parts.append(f"missing env vars: {', '.join(self.missing)}")
        if self.failures:
            parts.extend(self.failures)
        return "; ".join(parts)


# live 模式必须为 true 的环境变量
REQUIRED_LIVE_ENV_VARS = [
    "LIVE_TRADING_CONFIRMED",
    "RISK_CONFIG_LOADED",
    "TELEGRAM_ENABLED",
    "KILL_SWITCH_TESTED",
]

# live 模式必须存在的 OKX 密钥环境变量
REQUIRED_OKX_ENV_VARS = [
    "OKX_API_KEY",
    "OKX_API_SECRET",
    "OKX_API_PASSPHRASE",
]


def check_live_guard(dry_run: bool) -> LiveGuardResult:
    """检查是否允许启动 live 模式。

    参数：
        dry_run: 配置中的 dry_run 值

    返回：
        LiveGuardResult:
        - dry_run=True: 总是通过（无需检查）
        - dry_run=False: 必须所有环境变量满足
    """
    if dry_run:
        return LiveGuardResult(passed=True, missing=[], failures=[])

    missing: List[str] = []
    failures: List[str] = []

    # 检查 live 开关变量
    for var in REQUIRED_LIVE_ENV_VARS:
        val = os.environ.get(var, "false").lower()
        if val != "true":
            missing.append(var)

    # 检查 OKX 密钥
    for var in REQUIRED_OKX_ENV_VARS:
        val = os.environ.get(var, "")
        if not val:
            missing.append(var)

    # 额外检查：LIVE_TRADING_CONFIRMED 不能是占位符
    live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "")
    if live_confirmed in ("", "false", "False", "FALSE", "placeholder"):
        if "LIVE_TRADING_CONFIRMED" not in missing:
            missing.append("LIVE_TRADING_CONFIRMED")

    passed = len(missing) == 0 and len(failures) == 0
    return LiveGuardResult(passed=passed, missing=missing, failures=failures)


def assert_live_guard(dry_run: bool) -> None:
    """检查 live_guard，不通过则抛异常。

    供 ExecutionEngine 或启动脚本调用。
    """
    result = check_live_guard(dry_run)
    if not result.passed:
        raise PermissionError(
            f"live_guard check failed: {result.error_message}. "
            f"如需启动 live，请设置以上环境变量为 true/有效值。"
        )
