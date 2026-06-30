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
PRECHECK_SCRIPT = PROJECT_ROOT / "scripts" / "precheck_dryrun.py"

DEFAULT_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
]


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
        if not BACKTEST_RESULTS_DIR.exists():
            return None
        after = {f.stem.replace("backtest-result-", "") for f in BACKTEST_RESULTS_DIR.glob("backtest-result-*.zip")}
        new_ids = sorted(after - before)
        return new_ids[-1] if new_ids else None

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
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "")[-800:]
                raise RuntimeError(f"回测失败 (exit {proc.returncode}): {tail}")

            result_id = self._latest_backtest_id(existing)
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
        """将 .env 中的 OKX 密钥注入临时 dry-run 配置。"""
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        raw["dry_run"] = True
        raw["dataformat_ohlcv"] = "feather"
        ex = raw.setdefault("exchange", {})
        ex["key"] = os.environ.get("OKX_API_KEY", ex.get("key", ""))
        ex["secret"] = os.environ.get("OKX_API_SECRET", ex.get("secret", ""))
        ex["password"] = os.environ.get("OKX_API_PASSPHRASE", ex.get("password", ""))
        tmp = LOG_DIR / "dryrun_runtime_config.json"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return tmp

    def get_bot_state(self) -> BotState:
        with self._lock:
            if self._bot_proc and self._bot_proc.poll() is not None:
                self._bot_state.running = False
                self._bot_state.pid = None
                self._bot_proc = None
            elif self._bot_proc:
                self._bot_state.running = True
                self._bot_state.pid = self._bot_proc.pid
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
        with self._lock:
            if self._bot_proc and self._bot_proc.poll() is None:
                raise RuntimeError("Bot 已在运行中")

            if not DRYRUN_CONFIG.exists():
                raise FileNotFoundError(f"dry-run 配置不存在: {DRYRUN_CONFIG}")

            self._run_precheck(DRYRUN_CONFIG)
            runtime_cfg = self._inject_okx_keys(DRYRUN_CONFIG)
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            from quant_guard.services.strategy_manager import resolve_strategy_name

            class_name = resolve_strategy_name(strategy)
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
            return self.get_bot_state()

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
        content = TRADE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        return content[-lines:]

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
