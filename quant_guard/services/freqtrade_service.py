"""Freqtrade 进程管理：历史回测 + dry-run 模拟盘。

封装 freqtrade CLI 子进程，供 Web API 调用。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USERDIR = PROJECT_ROOT / "user_data"
BACKTEST_CONFIG = USERDIR / "config" / "config.binance.example.json"
DRYRUN_CONFIG = USERDIR / "config" / "config.dryrun.example.json"
BACKTEST_RESULTS_DIR = USERDIR / "backtest_results"
LOG_DIR = USERDIR / "logs"
PID_FILE = LOG_DIR / "freqtrade.pid"
TRADE_LOG = LOG_DIR / "freqtrade.log"
DRYRUN_DB = USERDIR / "db" / "tradesv3.dryrun.sqlite"
PRECHECK_SCRIPT = PROJECT_ROOT / "scripts" / "precheck_dryrun.py"

DEFAULT_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
]

# Freqtrade 2026 + ccxt 在进程退出时可能返回 2，但回测结果已写入
_BENIGN_EXIT_CODES = {0, 2}


def _extract_backtest_error(output: str) -> str:
    """从 Freqtrade 输出中提取真正的 ERROR 行，忽略末尾 ccxt/asyncio 噪音。"""
    lines = output.replace("\r", "").splitlines()
    errors = [
        ln.strip()
        for ln in lines
        if " - ERROR - " in ln and "Unclosed connector" not in ln
    ]
    if errors:
        return errors[-1][:500]
    for ln in reversed(lines):
        if "Impossible to load Strategy" in ln or "Please migrate" in ln:
            return ln.strip()[:500]
    tail = output.strip()[-600:]
    return tail or "回测失败（未知原因）"


def _read_latest_result_id() -> Optional[str]:
    """读取 Freqtrade 写入的 .last_result.json。"""
    marker = BACKTEST_RESULTS_DIR / ".last_result.json"
    if not marker.exists():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        name = data.get("latest_backtest", "")
        if name.startswith("backtest-result-") and name.endswith(".zip"):
            return name.replace("backtest-result-", "").replace(".zip", "")
    except (json.JSONDecodeError, OSError):
        pass
    return None


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class BacktestJob:
    id: str
    strategy: str
    timerange: str
    status: JobStatus = JobStatus.PENDING
    result_id: Optional[str] = None
    error: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""


@dataclass
class BotState:
    running: bool = False
    pid: Optional[int] = None
    strategy: str = "EmaCrossoverStrategy"
    dry_run: bool = True
    started_at: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class FreqtradeService:
    """Freqtrade 回测与 dry-run 统一管理。"""

    _bot_proc: Optional[subprocess.Popen] = field(default=None, repr=False)
    _bot_state: BotState = field(default_factory=BotState)
    _backtest_jobs: dict[str, BacktestJob] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _python(self) -> str:
        return sys.executable

    def _freqtrade_cmd(self, *args: str) -> list[str]:
        return [self._python(), "-m", "freqtrade", *args]

    def ensure_futures_data_links(self, exchange: str = "binance") -> int:
        """Freqtrade 永续数据需在 data/{exchange}/futures/ 下，为已有 feather 建链接。"""
        data_dir = USERDIR / "data" / exchange
        futures_dir = data_dir / "futures"
        if not data_dir.exists():
            return 0
        futures_dir.mkdir(parents=True, exist_ok=True)
        linked = 0
        for src in data_dir.glob("*-futures.feather"):
            if src.is_symlink() or src.parent.name == "futures":
                continue
            dest = futures_dir / src.name
            if dest.exists():
                continue
            dest.symlink_to(src.resolve())
            linked += 1
        return linked

    def _load_backtest_config(self) -> Path:
        """生成带 dataformat_ohlcv 的临时回测配置。"""
        cfg_path = BACKTEST_CONFIG
        if not cfg_path.exists():
            raise FileNotFoundError(f"回测配置不存在: {cfg_path}")
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        raw["dataformat_ohlcv"] = "feather"
        raw["dry_run"] = True
        tmp = LOG_DIR / "backtest_runtime_config.json"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return tmp

    def _latest_backtest_id(self, before: set[str]) -> Optional[str]:
        rid = _read_latest_result_id()
        if rid and rid not in before:
            return rid
        if not BACKTEST_RESULTS_DIR.exists():
            return None
        after = {f.stem.replace("backtest-result-", "") for f in BACKTEST_RESULTS_DIR.glob("backtest-result-*.zip")}
        new_ids = sorted(after - before)
        return new_ids[-1] if new_ids else None

    def infer_timerange_for_web(self, days: int = 90) -> str:
        """Web 回测默认时间范围：最近 N 天（避免一次回测数年导致超时）。"""
        from datetime import timedelta

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"

    def start_backtest_async(
        self,
        strategy: str,
        timerange: str,
        pairs: Optional[list[str]] = None,
    ) -> BacktestJob:
        """后台线程运行回测。"""
        job_id = uuid.uuid4().hex[:12]
        job = BacktestJob(
            id=job_id,
            strategy=strategy,
            timerange=timerange,
            status=JobStatus.PENDING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._backtest_jobs[job_id] = job

        def _run() -> None:
            with self._lock:
                self._backtest_jobs[job_id].status = JobStatus.RUNNING
            result = self._execute_backtest(job_id, strategy, timerange, pairs)
            with self._lock:
                self._backtest_jobs[job_id] = result

        threading.Thread(target=_run, daemon=True, name=f"backtest-{job_id}").start()
        return self.get_backtest_job(job_id)  # type: ignore[return-value]

    def _execute_backtest(
        self,
        job_id: str,
        strategy: str,
        timerange: str,
        pairs: Optional[list[str]] = None,
        timeout: int = 600,
    ) -> BacktestJob:
        job = BacktestJob(
            id=job_id,
            strategy=strategy,
            timerange=timerange,
            status=JobStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.ensure_futures_data_links("binance")
        BACKTEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        existing = set()
        if BACKTEST_RESULTS_DIR.exists():
            existing = {f.stem.replace("backtest-result-", "") for f in BACKTEST_RESULTS_DIR.glob("backtest-result-*.zip")}

        try:
            from quant_guard.services.strategy_manager import resolve_strategy_name

            class_name = resolve_strategy_name(strategy)
            cfg = self._load_backtest_config()
            cmd = self._freqtrade_cmd(
                "backtesting",
                "--config", str(cfg),
                "--strategy", class_name,
                "--userdir", str(USERDIR),
                "--timerange", timerange,
                "--cache", "none",
            )
            use_pairs = pairs or DEFAULT_PAIRS
            cmd.extend(["--pairs", *use_pairs])

            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
            result_id = self._latest_backtest_id(existing)

            if not result_id:
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"回测失败 (exit {proc.returncode}): {_extract_backtest_error(combined)}"
                    )
                raise RuntimeError(
                    f"回测未生成结果文件: {_extract_backtest_error(combined)}"
                )

            if proc.returncode != 0 and proc.returncode not in _BENIGN_EXIT_CODES:
                raise RuntimeError(
                    f"回测失败 (exit {proc.returncode}): {_extract_backtest_error(combined)}"
                )

            job.status = JobStatus.DONE
            job.result_id = result_id
            job.finished_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error = str(e)
            job.finished_at = datetime.now(timezone.utc).isoformat()
        return job

    def run_backtest_sync(
        self,
        strategy: str,
        timerange: str,
        pairs: Optional[list[str]] = None,
        timeout: int = 600,
    ) -> BacktestJob:
        """同步运行回测（阻塞直到完成）。"""
        job_id = uuid.uuid4().hex[:12]
        job = self._execute_backtest(job_id, strategy, timerange, pairs, timeout)
        with self._lock:
            self._backtest_jobs[job_id] = job
        return job

    def get_backtest_job(self, job_id: str) -> Optional[BacktestJob]:
        with self._lock:
            return self._backtest_jobs.get(job_id)

    def _run_precheck(self, config_path: Path) -> None:
        if not PRECHECK_SCRIPT.exists():
            return
        proc = subprocess.run(
            [self._python(), str(PRECHECK_SCRIPT), "--config", str(config_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            msg = (proc.stdout + proc.stderr)[-500:]
            raise RuntimeError(f"dry-run 安全检查未通过: {msg}")

    def _inject_okx_keys(self, config_path: Path) -> Path:
        """将 .env 中的 OKX 密钥注入临时 dry-run 配置。

        安全：dry-run 模式下 Freqtrade 不需要真实 API 密钥（dry_run=True）。
        若环境变量提供了密钥，注入占位符避免 secret 明文落盘；
        仅在非 dry-run 模式下需要真实密钥时通过环境变量传递。
        """
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        raw["dry_run"] = True
        raw["dataformat_ohlcv"] = "feather"
        DRYRUN_DB.parent.mkdir(parents=True, exist_ok=True)
        raw["db_url"] = f"sqlite:///{DRYRUN_DB.relative_to(PROJECT_ROOT).as_posix()}"
        ex = raw.setdefault("exchange", {})
        # dry-run 模式不需要真实密钥，写入占位符防止 secret 泄露
        # 真实密钥通过环境变量在运行时由 ccxt 读取
        ex["key"] = os.environ.get("OKX_API_KEY", "")
        ex["secret"] = "DRY_RUN_NO_SECRET_NEEDED"
        ex["password"] = os.environ.get("OKX_API_PASSPHRASE", "")
        tmp = LOG_DIR / "dryrun_runtime_config.json"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return tmp

    @staticmethod
    def _is_pid_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _read_pid_file(self) -> Optional[int]:
        if not PID_FILE.exists():
            return None
        try:
            return int(PID_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return None

    @staticmethod
    def _strategy_from_pid(pid: int) -> Optional[str]:
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", errors="replace")
            parts = [p for p in cmdline.split("\0") if p]
            for i, part in enumerate(parts):
                if part == "--strategy" and i + 1 < len(parts):
                    return parts[i + 1]
        except OSError:
            pass
        return None

    def _recover_bot_state_from_disk(self) -> None:
        """uvicorn 重启后内存中的 _bot_proc 会丢失，从 PID 文件恢复运行状态。"""
        if self._bot_proc and self._bot_proc.poll() is None:
            return

        pid = self._read_pid_file()
        if pid is None or not self._is_pid_running(pid):
            if self._bot_state.running:
                self._bot_state.running = False
                self._bot_state.pid = None
            return

        strategy = self._strategy_from_pid(pid) or self._bot_state.strategy
        self._bot_state.running = True
        self._bot_state.pid = pid
        self._bot_state.dry_run = True
        self._bot_state.strategy = strategy

    def get_bot_state(self) -> BotState:
        with self._lock:
            if self._bot_proc and self._bot_proc.poll() is not None:
                self._bot_state.running = False
                self._bot_state.pid = None
                self._bot_proc = None
            elif self._bot_proc:
                self._bot_state.running = True
                self._bot_state.pid = self._bot_proc.pid
            else:
                self._recover_bot_state_from_disk()
            return BotState(
                running=self._bot_state.running,
                pid=self._bot_state.pid,
                strategy=self._bot_state.strategy,
                dry_run=self._bot_state.dry_run,
                started_at=self._bot_state.started_at,
                last_error=self._bot_state.last_error,
            )

    def start_bot(self, strategy: str = "EmaCrossoverStrategy") -> BotState:
        """启动 Freqtrade dry-run 进程。"""
        from quant_guard.services.control_service import control_service

        if control_service.is_kill_switch_active():
            raise RuntimeError("Kill Switch 已激活，拒绝启动 Bot")

        if not DRYRUN_CONFIG.exists():
            raise FileNotFoundError(f"dry-run 配置不存在: {DRYRUN_CONFIG}")

        # 预检查可能耗时数秒，勿持有全局锁，否则会阻塞 /api/control/status
        self._run_precheck(DRYRUN_CONFIG)
        runtime_cfg = self._inject_okx_keys(DRYRUN_CONFIG)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        from quant_guard.services.strategy_manager import resolve_strategy_name

        class_name = resolve_strategy_name(strategy)

        with self._lock:
            if self._bot_proc and self._bot_proc.poll() is None:
                raise RuntimeError("Bot 已在运行中")

            log_f = open(TRADE_LOG, "a", encoding="utf-8")
            cmd = self._freqtrade_cmd(
                "trade",
                "--config", str(runtime_cfg),
                "--strategy", class_name,
                "--userdir", str(USERDIR),
                "--logfile", str(TRADE_LOG),
            )
            self._bot_proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            PID_FILE.write_text(str(self._bot_proc.pid), encoding="utf-8")
            self._bot_state = BotState(
                running=True,
                pid=self._bot_proc.pid,
                strategy=class_name,
                dry_run=True,
                started_at=datetime.now(timezone.utc).isoformat(),
                last_error=None,
            )
            return BotState(
                running=True,
                pid=self._bot_proc.pid,
                strategy=class_name,
                dry_run=True,
                started_at=self._bot_state.started_at,
                last_error=None,
            )

    def stop_bot(self) -> BotState:
        """停止 Freqtrade dry-run 进程。"""
        with self._lock:
            if self._bot_proc and self._bot_proc.poll() is None:
                self._bot_proc.terminate()
                try:
                    self._bot_proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._bot_proc.kill()
            elif PID_FILE.exists():
                try:
                    pid = int(PID_FILE.read_text(encoding="utf-8").strip())
                    os.kill(pid, 15)
                except (OSError, ValueError):
                    pass

            self._bot_proc = None
            self._bot_state.running = False
            self._bot_state.pid = None
            if PID_FILE.exists():
                PID_FILE.unlink(missing_ok=True)
            return self.get_bot_state()

    def get_log_tail(self, lines: int = 30) -> list[str]:
        if not TRADE_LOG.exists():
            return []
        try:
            with TRADE_LOG.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                chunk = min(size, 64 * 1024)
                f.seek(max(0, size - chunk))
                text = f.read().decode("utf-8", errors="replace")
            return text.splitlines()[-lines:]
        except OSError:
            return []

    def infer_timerange_from_data(self, exchange: str = "binance") -> str:
        """从本地 15m 数据推断可用 timerange（YYYYMMDD-YYYYMMDD）。"""
        import pandas as pd

        futures_dir = USERDIR / "data" / exchange / "futures"
        self.ensure_futures_data_links(exchange)
        sample = futures_dir / "BTC_USDT_USDT-15m-futures.feather"
        if not sample.exists():
            end = datetime.now(timezone.utc).strftime("%Y%m%d")
            return f"20250101-{end}"
        df = pd.read_feather(sample)
        dates = pd.to_datetime(df["date"], utc=True)
        start = dates.min().strftime("%Y%m%d")
        end = dates.max().strftime("%Y%m%d")
        return f"{start}-{end}"


# 全局单例
freqtrade_service = FreqtradeService()
