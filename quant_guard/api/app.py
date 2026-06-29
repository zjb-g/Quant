"""FastAPI 应用主入口。

提供仪表盘/回测/控制/告警 4 组 REST API，封装 quant_guard 模块。
"""

import json
import os
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
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


@app.get("/api/backtest/list")
def list_backtests():
    """列出可用的回测结果，返回 {id, strategy, timestamp} 列表。"""
    if not BACKTEST_RESULTS_DIR.exists():
        return []
    results = []
    for f in BACKTEST_RESULTS_DIR.glob("backtest-result-*.zip"):
        ts = f.stem.replace("backtest-result-", "")
        strategy_name = ""
        try:
            with zipfile.ZipFile(f) as zf:
                json_names = [n for n in zf.namelist() if n.endswith(".json")]
                if json_names:
                    data = json.loads(zf.read(json_names[0]).decode("utf-8"))
                    strategies = list(data.get("strategy", {}).keys())
                    strategy_name = strategies[0] if strategies else ""
        except Exception:
            pass
        results.append({"id": ts, "strategy": strategy_name, "timestamp": ts})
    return sorted(results, key=lambda x: x["timestamp"], reverse=True)


@app.get("/api/backtest/{backtest_id}")
def get_backtest_result(backtest_id: str):
    """获取指定回测结果的摘要和交易明细。从 zip 中读取 JSON。"""
    # 查找对应的 zip 文件
    zip_file = BACKTEST_RESULTS_DIR / f"backtest-result-{backtest_id}.zip"
    if not zip_file.exists():
        # 模糊匹配
        candidates = list(BACKTEST_RESULTS_DIR.glob(f"*{backtest_id}*.zip"))
        if not candidates:
            raise HTTPException(status_code=404, detail="backtest not found")
        zip_file = candidates[0]

    # 从 zip 读取 JSON
    with zipfile.ZipFile(zip_file) as zf:
        json_names = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_names:
            raise HTTPException(status_code=500, detail="no json in zip")
        with zf.open(json_names[0]) as f:
            raw = json.loads(f.read().decode("utf-8"))

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


# ================================================================== #
# 策略管理 API
# ================================================================== #

class StrategyGenerateRequest(BaseModel):
    description: str
    filename: str = ""


class StrategySaveRequest(BaseModel):
    filename: str
    code: str


class StrategyRefineRequest(BaseModel):
    code: str
    feedback: str


@app.get("/api/strategies")
def list_strategies_api():
    """列出所有策略文件。"""
    from quant_guard.services.strategy_manager import list_strategies
    strategies = list_strategies()
    return [
        {
            "filename": s.filename,
            "name": s.name,
            "description": s.description,
            "size": s.size,
            "has_errors": s.has_errors,
            "error_msg": s.error_msg,
        }
        for s in strategies
    ]


@app.get("/api/strategies/{filename}")
def get_strategy_api(filename: str):
    """读取策略代码。"""
    from quant_guard.services.strategy_manager import get_strategy_code
    code = get_strategy_code(filename)
    if code is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"filename": filename, "code": code}


@app.post("/api/strategies")
def save_strategy_api(req: StrategySaveRequest):
    """保存/更新策略代码。"""
    from quant_guard.services.strategy_manager import save_strategy
    try:
        path = save_strategy(req.filename, req.code)
        _add_alert("INFO", "strategy_saved", f"策略 {req.filename} 已保存")
        return {"status": "saved", "filename": req.filename, "path": str(path)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/strategies/{filename}")
def delete_strategy_api(filename: str):
    """删除策略文件。"""
    from quant_guard.services.strategy_manager import delete_strategy
    ok = delete_strategy(filename)
    if not ok:
        raise HTTPException(status_code=404, detail="策略不存在")
    _add_alert("WARNING", "strategy_deleted", f"策略 {filename} 已删除")
    return {"status": "deleted"}


# ================================================================== #
# AI 策略生成 API（DeepSeek）
# ================================================================== #

@app.post("/api/ai/generate-strategy")
def ai_generate_strategy(req: StrategyGenerateRequest):
    """用自然语言描述生成 Freqtrade 策略代码（DeepSeek AI）。"""
    from quant_guard.ai.deepseek import DeepSeekClient
    client = DeepSeekClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=400,
            detail="DeepSeek API 未配置。请在 .env 中设置 DEEPSEEK_API_KEY=sk-xxx",
        )
    try:
        code = client.generate_strategy(req.description)
        _add_alert("INFO", "ai_strategy_generated", f"AI 生成策略: {req.description[:50]}...")
        # 如果提供了文件名，自动保存
        filename = req.filename or "AIGeneratedStrategy.py"
        return {"code": code, "filename": filename, "description": req.description}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/refine-strategy")
def ai_refine_strategy(req: StrategyRefineRequest):
    """根据反馈修改已有策略代码。"""
    from quant_guard.ai.deepseek import DeepSeekClient
    client = DeepSeekClient()
    if not client.is_configured:
        raise HTTPException(status_code=400, detail="DeepSeek API 未配置")
    try:
        code = client.refine_strategy(req.code, req.feedback)
        return {"code": code}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/status")
def ai_status():
    """检查 AI 服务是否已配置。"""
    from quant_guard.ai.deepseek import DeepSeekClient
    client = DeepSeekClient()
    return {"configured": client.is_configured, "model": client.model}


# ================================================================== #
# 交易所连接 + 真实数据 API
# ================================================================== #

class EnvUpdateRequest(BaseModel):
    """环境变量更新请求（运行时，不持久化到 .env 文件）。"""
    vars: dict


@app.get("/api/exchange/status")
def exchange_status():
    """检查交易所连接状态。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    conn = svc.test_connection()
    return {
        "connected": conn.connected,
        "exchange": conn.exchange,
        "error": conn.error,
        "account_mode": conn.account_mode,
    }


@app.post("/api/exchange/config")
def exchange_config(req: EnvUpdateRequest):
    """配置交易所 API Key（运行时设置环境变量，不写入文件）。"""
    import os
    for key, value in req.vars.items():
        if value:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]
    _add_alert("INFO", "exchange_configured", f"交易所环境变量已更新: {list(req.vars.keys())}")
    return {"status": "updated", "keys": list(req.vars.keys())}


@app.get("/api/exchange/balance")
def exchange_balance():
    """获取账户余额。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    try:
        bal = svc.get_balance()
        return {"total": bal.total, "free": bal.free, "used": bal.used, "currency": bal.currency}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取余额失败: {e}")


@app.get("/api/exchange/positions")
def exchange_positions():
    """获取当前真实持仓。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    try:
        return svc.get_positions()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {e}")


@app.get("/api/exchange/trades")
def exchange_trades(limit: int = 100):
    """获取历史交易记录。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    try:
        trades = svc.get_historical_trades(limit)
        return [
            {
                "id": t.id,
                "timestamp": t.timestamp,
                "symbol": t.symbol,
                "side": t.side,
                "amount": t.amount,
                "price": t.price,
                "fee": t.fee,
                "pnl": t.pnl,
            }
            for t in trades
        ]
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易记录失败: {e}")


@app.get("/api/exchange/orders")
def exchange_orders():
    """获取当前挂单。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    try:
        return svc.get_open_orders()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取挂单失败: {e}")


@app.post("/api/exchange/test")
def exchange_test(req: EnvUpdateRequest):
    """设置 API Key 并测试连接（一步完成）。"""
    import os
    for key, value in req.vars.items():
        if value:
            os.environ[key] = value
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    # 重置已缓存的连接
    svc._exchange = None
    svc._exchange_name = ""
    conn = svc.test_connection()
    if conn.connected:
        _add_alert("INFO", "exchange_connected", f"交易所 {conn.exchange} 连接成功")
    else:
        _add_alert("WARNING", "exchange_connect_failed", f"交易所连接失败: {conn.error}")
    return {
        "connected": conn.connected,
        "exchange": conn.exchange,
        "error": conn.error,
    }


# ================================================================== #
# 环境变量管理 API
# ================================================================== #

@app.get("/api/env")
def get_env():
    """获取当前环境变量配置状态（不返回值，只返回是否已设置）。"""
    keys = [
        "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE",
        "GATE_API_KEY", "GATE_API_SECRET",
        "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "LIVE_TRADING_CONFIRMED", "RISK_CONFIG_LOADED",
    ]
    return {k: bool(os.environ.get(k, "")) for k in keys}


@app.on_event("startup")
def on_startup():
    """启动时记录。"""
    _add_alert("INFO", "api_started", "FastAPI backend started")
