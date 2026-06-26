"""FastAPI 应用主入口。

提供仪表盘/回测/控制/告警 4 组 REST API，封装 quant_guard 模块。
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Crypto Quant System API",
    description="个人加密永续合约量化交易系统后端",
    version="0.1.0",
)

# CORS：允许前端开发跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 数据模型 ----------


class SystemStatus(BaseModel):
    bot_running: bool
    dry_run: bool
    strategy: str
    exchange: str
    uptime_seconds: int
    current_time: str


class Position(BaseModel):
    symbol: str
    side: str
    contracts: float
    entry_price: float
    mark_price: float
    leverage: float
    unrealized_pnl: float
    liquidation_price: Optional[float] = None


class EquityPoint(BaseModel):
    timestamp: str
    equity: float
    drawdown_pct: float


class RiskState(BaseModel):
    kill_switch: bool
    kill_switch_reason: Optional[str] = None
    max_leverage: int
    max_total_notional: float
    current_total_notional: float
    equity_high_watermark: float
    current_equity: float
    max_drawdown_pct: float
    daily_start_equity: float
    daily_loss_pct: float
    daily_loss_limit_pct: float


class RiskConfig(BaseModel):
    max_single_order_notional: float = 200
    max_symbol_notional: float = 300
    max_total_notional: float = 1000
    max_leverage: int = 5
    max_drawdown_stop_pct: float = 15
    daily_loss_stop_pct: float = 5
    liquidation_distance_pct: float = 10


class KillSwitchRequest(BaseModel):
    reason: str = "manual"


class EmergencyCloseRequest(BaseModel):
    confirm: bool = False


class BacktestSummary(BaseModel):
    strategy: str
    timerange: str
    total_trades: int
    total_profit_pct: float
    max_drawdown_pct: float
    win_rate: float
    avg_duration: str
    sharpe: float
    sortino: float


class BacktestTrade(BaseModel):
    pair: str
    open_date: str
    close_date: str
    side: str
    open_rate: float
    close_rate: float
    profit_pct: float
    profit_abs: float
    exit_reason: str


class AlertEvent(BaseModel):
    id: str
    timestamp: str
    level: str
    type: str
    message: str


# ---------- 全局状态（TODO: 后续任务接入真实 quant_guard 模块）----------

_RISK_CONFIG = RiskConfig()
_RISK_STATE = RiskState(
    kill_switch=False,
    kill_switch_reason=None,
    max_leverage=5,
    max_total_notional=1000,
    current_total_notional=0,
    equity_high_watermark=1000,
    current_equity=1000,
    max_drawdown_pct=0,
    daily_start_equity=1000,
    daily_loss_pct=0,
    daily_loss_limit_pct=5,
)
_BOT_RUNNING = False
_START_TIME: Optional[datetime] = None
_ALERTS: list[AlertEvent] = []

BACKTEST_RESULTS_DIR = Path("user_data/backtest_results")


def _add_alert(level: str, alert_type: str, message: str) -> None:
    _ALERTS.insert(0, AlertEvent(
        id=f"{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        level=level,
        type=alert_type,
        message=message,
    ))
    if len(_ALERTS) > 500:
        _ALERTS[:] = _ALERTS[:500]


# ---------- 仪表盘 API ----------


@app.get("/api/status", response_model=SystemStatus)
def get_status():
    """获取系统状态。"""
    uptime = int((datetime.now(timezone.utc) - _START_TIME).total_seconds()) if _START_TIME else 0
    return SystemStatus(
        bot_running=_BOT_RUNNING,
        dry_run=True,
        strategy="EmaCrossoverStrategy",
        exchange="okx",
        uptime_seconds=uptime,
        current_time=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/positions", response_model=list[Position])
def get_positions():
    """获取当前持仓。当前为占位，后续接入 OKXClient.get_positions()。"""
    return []


@app.get("/api/equity", response_model=list[EquityPoint])
def get_equity(days: int = 30):
    """获取权益曲线。当前为占位，后续接入 RiskState 历史。"""
    return []


@app.get("/api/risk/state", response_model=RiskState)
def get_risk_state():
    """获取风控状态。"""
    return _RISK_STATE


# ---------- 回测 API ----------


@app.get("/api/backtest/list", response_model=list[str])
def list_backtests():
    """列出可用的回测结果 ID。"""
    if not BACKTEST_RESULTS_DIR.exists():
        return []
    ids = []
    for f in BACKTEST_RESULTS_DIR.glob("*.json"):
        if "meta" not in f.name:
            ids.append(f.stem)
    return sorted(ids, reverse=True)


@app.get("/api/backtest/{backtest_id}")
def get_backtest_result(backtest_id: str):
    """获取指定回测结果的摘要和交易明细。"""
    # 尝试读取 Freqtrade 回测结果 JSON
    result_file = BACKTEST_RESULTS_DIR / f"{backtest_id}.json"
    if not result_file.exists():
        # 查找带时间戳的文件
        candidates = list(BACKTEST_RESULTS_DIR.glob(f"*{backtest_id}*.json"))
        candidates = [c for c in candidates if "meta" not in c.name]
        if not candidates:
            raise HTTPException(status_code=404, detail="backtest not found")
        result_file = candidates[0]

    with open(result_file, encoding="utf-8") as f:
        raw = json.load(f)

    strategy = raw.get("strategy", {})
    strategy_name = list(strategy.keys())[0] if strategy else "unknown"
    s = strategy.get(strategy_name, {})

    trades_raw = s.get("trades", [])
    trades = [
        BacktestTrade(
            pair=t.get("pair", ""),
            open_date=t.get("open_date", ""),
            close_date=t.get("close_date", ""),
            side="long" if t.get("is_short", False) is False else "short",
            open_rate=t.get("open_rate", 0),
            close_rate=t.get("close_rate", 0),
            profit_pct=t.get("profit_ratio", 0) * 100,
            profit_abs=t.get("profit_abs", 0),
            exit_reason=t.get("exit_reason", ""),
        )
        for t in trades_raw
    ]

    summary = BacktestSummary(
        strategy=strategy_name,
        timerange=f"{s.get('backtest_start', '')} ~ {s.get('backtest_end', '')}",
        total_trades=s.get("total_trades", 0),
        total_profit_pct=s.get("profit_total", 0),
        max_drawdown_pct=s.get("max_drawdown_abs", 0),
        win_rate=(s.get("wins", 0) / max(s.get("total_trades", 1), 1)) * 100,
        avg_duration=str(s.get("holding_avg", "")),
        sharpe=s.get("sharpe", 0),
        sortino=s.get("sortino", 0),
    )

    return {"summary": summary, "trades": trades}


# ---------- 控制 API ----------


@app.post("/api/control/start")
def start_bot():
    """启动 Bot。"""
    global _BOT_RUNNING, _START_TIME
    _BOT_RUNNING = True
    _START_TIME = datetime.now(timezone.utc)
    _add_alert("INFO", "bot_started", "Bot started via Web UI")
    return {"status": "started"}


@app.post("/api/control/stop")
def stop_bot():
    """停止 Bot。"""
    global _BOT_RUNNING
    _BOT_RUNNING = False
    _add_alert("INFO", "bot_stopped", "Bot stopped via Web UI")
    return {"status": "stopped"}


@app.post("/api/control/kill-switch")
def activate_kill_switch(req: KillSwitchRequest):
    """激活 Kill Switch。"""
    global _RISK_STATE
    _RISK_STATE = _RISK_STATE.model_copy(update={
        "kill_switch": True,
        "kill_switch_reason": req.reason,
    })
    _add_alert("CRITICAL", "kill_switch_activated", f"Kill switch activated: {req.reason}")
    return {"status": "kill_switch_activated", "reason": req.reason}


@app.post("/api/control/emergency-close")
def emergency_close(req: EmergencyCloseRequest):
    """紧急全平。必须 confirm=True 才执行。"""
    if not req.confirm:
        _add_alert("WARNING", "emergency_close_rejected", "Emergency close rejected: no confirmation")
        raise HTTPException(status_code=400, detail="confirmation required")
    # TODO T3.5: 接入真实 emergency_close_all
    _add_alert("CRITICAL", "emergency_close_executed", "Emergency close all executed via Web UI")
    return {"status": "emergency_close_executed"}


# ---------- 风控配置 API ----------


@app.get("/api/risk/config", response_model=RiskConfig)
def get_risk_config():
    """获取风控配置。"""
    return _RISK_CONFIG


@app.put("/api/risk/config", response_model=RiskConfig)
def update_risk_config(config: RiskConfig):
    """更新风控配置。"""
    global _RISK_CONFIG
    _RISK_CONFIG = config
    _add_alert("INFO", "risk_config_updated", f"Risk config updated via Web UI")
    return _RISK_CONFIG


# ---------- 告警 API ----------


@app.get("/api/alerts", response_model=list[AlertEvent])
def get_alerts(limit: int = 100):
    """获取告警事件列表。"""
    return _ALERTS[:limit]


@app.on_event("startup")
def on_startup():
    """启动时记录。"""
    _add_alert("INFO", "api_started", "FastAPI backend started")
