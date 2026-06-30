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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from quant_guard.backtest.report import _max_drawdown_pct, _profit_total_pct

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


class BotStartRequest(BaseModel):
    strategy: str = "EmaCrossoverStrategy"


class BacktestRunRequest(BaseModel):
    strategy: str = "EmaCrossoverStrategy"
    timerange: str = ""
    pairs: list[str] = []
    async_run: bool = True


class BacktestJobResponse(BaseModel):
    id: str
    strategy: str
    timerange: str
    status: str
    result_id: Optional[str] = None
    error: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""


class BotStatusResponse(BaseModel):
    running: bool
    pid: Optional[int] = None
    strategy: str
    dry_run: bool
    started_at: Optional[str] = None
    last_error: Optional[str] = None
    log_tail: list[str] = []


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


class PositionHistory(BaseModel):
    position_id: str
    symbol: str
    side: str
    leverage: float
    margin_mode: str
    open_avg_price: float
    close_avg_price: float
    close_size: float
    pnl: float
    realized_pnl: float
    pnl_ratio: float
    fee: float
    funding_fee: float
    close_type: str
    open_time: str
    close_time: str


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
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _load_dotenv() -> None:
    """加载 .env（若存在）。"""
    env_path = Path(".env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            pass


def _position_history_to_api(h) -> PositionHistory:
    return PositionHistory(
        position_id=h.position_id,
        symbol=h.symbol,
        side=h.side.value,
        leverage=h.leverage,
        margin_mode=h.margin_mode,
        open_avg_price=h.open_avg_price,
        close_avg_price=h.close_avg_price,
        close_size=h.close_size,
        pnl=h.pnl,
        realized_pnl=h.realized_pnl,
        pnl_ratio=h.pnl_ratio,
        fee=h.fee,
        funding_fee=h.funding_fee,
        close_type=h.close_type.value,
        open_time=datetime.fromtimestamp(h.open_time / 1000, tz=timezone.utc).isoformat()
        if h.open_time
        else "",
        close_time=datetime.fromtimestamp(h.close_time / 1000, tz=timezone.utc).isoformat()
        if h.close_time
        else "",
    )


def _position_history_to_dict(p: PositionHistory) -> dict:
    return p.model_dump()


def _query_positions_history(
    positions: list[PositionHistory],
    *,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    close_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    position_ids: Optional[str] = None,
    close_times: Optional[str] = None,
    sort_by: str = "close_time",
    order: str = "desc",
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
) -> list[PositionHistory]:
    from quant_guard.services.trade_analysis_service import filter_positions, sort_positions

    id_set = {x.strip() for x in position_ids.split(",") if x.strip()} if position_ids else None
    ct_set = {x.strip() for x in close_times.split(",") if x.strip()} if close_times else None
    dict_rows = [_position_history_to_dict(p) for p in positions]
    rows = filter_positions(
        dict_rows,
        symbol=symbol,
        side=side,
        close_type=close_type,
        start_time=start_time,
        end_time=end_time,
        position_ids=id_set,
        close_times=ct_set,
        min_pnl=min_pnl,
        max_pnl=max_pnl,
    )
    rows = sort_positions(rows, sort_by=sort_by, order=order)
    return [PositionHistory(**r) for r in rows]


def _get_okx_client():
    """获取 OKX 私有客户端，未配置密钥时抛 HTTPException。"""
    from quant_guard.exchange.okx_client import OKXClient, OKXClientError

    _load_dotenv()
    try:
        return OKXClient(public_only=False)
    except OKXClientError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


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
    from quant_guard.services.freqtrade_service import freqtrade_service

    bot = freqtrade_service.get_bot_state()
    uptime = int((datetime.now(timezone.utc) - _START_TIME).total_seconds()) if _START_TIME and bot.running else 0
    if bot.running and bot.started_at and not _START_TIME:
        pass  # use bot started_at below if needed
    if bot.running and bot.started_at:
        try:
            started = datetime.fromisoformat(bot.started_at.replace("Z", "+00:00"))
            uptime = int((datetime.now(timezone.utc) - started).total_seconds())
        except ValueError:
            uptime = 0
    return SystemStatus(
        bot_running=bot.running,
        dry_run=bot.dry_run,
        strategy=bot.strategy,
        exchange="okx",
        uptime_seconds=uptime,
        current_time=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/positions", response_model=list[Position])
def get_positions():
    """获取当前持仓（接入 OKXClient）。"""
    try:
        client = _get_okx_client()
        positions = client.get_positions()
        return [
            Position(
                symbol=p.symbol,
                side=p.side.value,
                contracts=p.contracts,
                entry_price=p.entry_price,
                mark_price=p.mark_price,
                leverage=p.leverage,
                unrealized_pnl=p.unrealized_pnl,
                liquidation_price=p.liquidation_price,
            )
            for p in positions
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {e}") from e


@app.get("/api/positions/history", response_model=list[PositionHistory])
def get_positions_history(
    limit: int = 50,
    all: bool = False,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    close_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    position_ids: Optional[str] = None,
    sort_by: str = "close_time",
    order: str = "desc",
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
):
    """获取历史持仓（已平仓记录）。支持筛选与排序。"""
    try:
        client = _get_okx_client()
        history = client.get_positions_history(
            limit=0 if all else limit, fetch_all=all
        )
        rows = [_position_history_to_api(h) for h in history]
        return _query_positions_history(
            rows,
            symbol=symbol,
            side=side,
            close_type=close_type,
            start_time=start_time,
            end_time=end_time,
            position_ids=position_ids,
            sort_by=sort_by,
            order=order,
            min_pnl=min_pnl,
            max_pnl=max_pnl,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史持仓失败: {e}") from e


@app.get("/api/positions/history/analyze")
def analyze_positions_history(
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    all: bool = True,
):
    """历史持仓统计分析（胜率、杠杆/持仓时长分组等）。"""
    from quant_guard.services.trade_analysis_service import analyze_positions

    try:
        client = _get_okx_client()
        history = client.get_positions_history(limit=0 if all else 200, fetch_all=all)
        rows = [_position_history_to_api(h) for h in history]
        filtered = _query_positions_history(
            rows,
            symbol=symbol,
            side=side,
            start_time=start_time,
            end_time=end_time,
        )
        stats = analyze_positions([_position_history_to_dict(p) for p in filtered])
        return {"stats": stats, "filtered_count": len(filtered), "total_count": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析历史持仓失败: {e}") from e


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


def _job_to_response(job) -> BacktestJobResponse:
    return BacktestJobResponse(
        id=job.id,
        strategy=job.strategy,
        timerange=job.timerange,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        result_id=job.result_id,
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@app.get("/api/backtest/timerange-default")
def backtest_default_timerange():
    """返回本地 K 线数据可用的默认 timerange。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    return {"timerange": freqtrade_service.infer_timerange_from_data()}


@app.post("/api/backtest/run", response_model=BacktestJobResponse)
def run_backtest(req: BacktestRunRequest):
    """在历史 K 线上运行 Freqtrade 回测。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    timerange = req.timerange.strip()
    if not timerange:
        timerange = freqtrade_service.infer_timerange_from_data()

    pairs = req.pairs if req.pairs else None
    if req.async_run:
        job = freqtrade_service.start_backtest_async(req.strategy, timerange, pairs)
    else:
        job = freqtrade_service.run_backtest_sync(req.strategy, timerange, pairs)
    _add_alert("INFO", "backtest_started", f"Backtest {req.strategy} {timerange}")
    return _job_to_response(job)


@app.get("/api/backtest/jobs/{job_id}", response_model=BacktestJobResponse)
def get_backtest_job(job_id: str):
    """查询回测任务状态。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    job = freqtrade_service.get_backtest_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    return _job_to_response(job)


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
        total_profit_pct=_profit_total_pct(s),
        max_drawdown_pct=_max_drawdown_pct(s),
        win_rate=(s.get("wins", 0) / max(s.get("total_trades", 1), 1)) * 100,
        avg_duration=str(s.get("holding_avg", "")),
        sharpe=s.get("sharpe", 0),
        sortino=s.get("sortino", 0),
    )

    return {"summary": summary, "trades": trades}


# ---------- 控制 API ----------


@app.post("/api/control/start")
def start_bot(req: BotStartRequest = BotStartRequest()):
    """启动 Freqtrade dry-run Bot。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    global _BOT_RUNNING, _START_TIME
    try:
        state = freqtrade_service.start_bot(req.strategy)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {e}") from e

    _BOT_RUNNING = True
    _START_TIME = datetime.now(timezone.utc)
    _add_alert("INFO", "bot_started", f"Freqtrade dry-run started: {req.strategy}")
    return {"status": "started", "pid": state.pid, "strategy": state.strategy}


@app.post("/api/control/stop")
def stop_bot():
    """停止 Freqtrade dry-run Bot。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    global _BOT_RUNNING
    state = freqtrade_service.stop_bot()
    _BOT_RUNNING = False
    _add_alert("INFO", "bot_stopped", "Freqtrade dry-run stopped via Web UI")
    return {"status": "stopped", "pid": state.pid}


@app.get("/api/control/status", response_model=BotStatusResponse)
def get_bot_status():
    """获取 Bot 进程真实状态。"""
    from quant_guard.services.freqtrade_service import freqtrade_service

    state = freqtrade_service.get_bot_state()
    return BotStatusResponse(
        running=state.running,
        pid=state.pid,
        strategy=state.strategy,
        dry_run=state.dry_run,
        started_at=state.started_at,
        last_error=state.last_error,
        log_tail=freqtrade_service.get_log_tail(20),
    )


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
            "id": Path(s.filename).stem,
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


class TradeAnalyzeRequest(BaseModel):
    symbol: Optional[str] = None
    side: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@app.post("/api/ai/analyze-trades")
def ai_analyze_trades(req: TradeAnalyzeRequest):
    """AI 分析历史持仓交易模式与改进建议。"""
    from quant_guard.ai.deepseek import DeepSeekClient
    from quant_guard.services.trade_analysis_service import analyze_positions

    client = DeepSeekClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=400,
            detail="DeepSeek API 未配置。请在 .env 中设置 DEEPSEEK_API_KEY=sk-xxx",
        )
    try:
        okx = _get_okx_client()
        history = okx.get_positions_history(fetch_all=True)
        rows = [_position_history_to_api(h) for h in history]
        filtered = _query_positions_history(
            rows,
            symbol=req.symbol,
            side=req.side,
            start_time=req.start_time,
            end_time=req.end_time,
        )
        dict_rows = [_position_history_to_dict(p) for p in filtered]
        stats = analyze_positions(dict_rows)
        analysis = client.analyze_trades(stats, dict_rows)
        _add_alert("INFO", "ai_trade_analysis", "AI 完成历史持仓分析")
        return {"analysis": analysis, "stats": stats, "trade_count": len(filtered)}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/api/exchange/positions/history", response_model=list[PositionHistory])
def exchange_positions_history(
    limit: int = 50,
    all: bool = False,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    close_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    position_ids: Optional[str] = None,
    sort_by: str = "close_time",
    order: str = "desc",
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
):
    """获取历史持仓（已平仓记录）。支持筛选与排序。"""
    from quant_guard.services.exchange_service import ExchangeService
    svc = ExchangeService()
    try:
        history = svc.get_positions_history(
            limit=0 if all else limit, fetch_all=all
        )
        rows = [
            PositionHistory(
                position_id=h.position_id,
                symbol=h.symbol,
                side=h.side,
                leverage=h.leverage,
                margin_mode=h.margin_mode,
                open_avg_price=h.open_avg_price,
                close_avg_price=h.close_avg_price,
                close_size=h.close_size,
                pnl=h.pnl,
                realized_pnl=h.realized_pnl,
                pnl_ratio=h.pnl_ratio,
                fee=h.fee,
                funding_fee=h.funding_fee,
                close_type=h.close_type,
                open_time=h.open_time,
                close_time=h.close_time,
            )
            for h in history
        ]
        return _query_positions_history(
            rows,
            symbol=symbol,
            side=side,
            close_type=close_type,
            start_time=start_time,
            end_time=end_time,
            position_ids=position_ids,
            sort_by=sort_by,
            order=order,
            min_pnl=min_pnl,
            max_pnl=max_pnl,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史持仓失败: {e}")


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
# 持仓复盘 K 线 API
# ================================================================== #


class ChartCandle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartMarker(BaseModel):
    position_id: str
    marker_type: str
    time: int
    price: float
    side: str
    pnl: float
    leverage: float
    close_type: str
    label: str


class ChartReviewResponse(BaseModel):
    symbol: str
    interval: str
    data_source: str
    candles: list[ChartCandle]
    markers: list[ChartMarker]
    positions: list[PositionHistory]
    total_pnl: float


@app.get("/api/chart/symbols")
def chart_symbols():
    """列出本地有 K 线数据的币种及可用周期。"""
    from quant_guard.services.kline_service import list_available_symbols

    return list_available_symbols()


@app.get("/api/chart/review", response_model=ChartReviewResponse)
def chart_review(
    symbol: str,
    interval: str = "15m",
    limit: int = 3000,
    position_ids: Optional[str] = None,
    close_times: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    marker_mode: str = "all",
):
    """获取 K 线 + 历史持仓进出场标注。

    marker_mode: all | time_range | selected
    """
    from quant_guard.services.kline_service import (
        build_markers,
        compute_chart_window_ms,
        load_candles,
        normalize_inst,
        _parse_iso_ms,
        _symbol_matches,
    )
    from quant_guard.services.trade_analysis_service import filter_positions

    inst = normalize_inst(symbol)
    positions_api: list[PositionHistory] = []
    try:
        client = _get_okx_client()
        raw = client.get_positions_history(fetch_all=True)
        for h in raw:
            if _symbol_matches(h.symbol, inst):
                positions_api.append(_position_history_to_api(h))
    except HTTPException:
        pass

    id_set = {x.strip() for x in position_ids.split(",") if x.strip()} if position_ids else None
    ct_set = {x.strip() for x in close_times.split(",") if x.strip()} if close_times else None
    chart_positions = filter_positions(
        [_position_history_to_dict(p) for p in positions_api],
        position_ids=id_set,
        close_times=ct_set,
        start_time=start_time if marker_mode == "time_range" else None,
        end_time=end_time if marker_mode == "time_range" else None,
    )
    if marker_mode == "selected" and (id_set or ct_set):
        chart_positions = filter_positions(
            [_position_history_to_dict(p) for p in positions_api],
            position_ids=id_set,
            close_times=ct_set,
        )
    elif marker_mode == "none":
        chart_positions = []

    start_ms = _parse_iso_ms(start_time) if start_time else None
    end_ms = _parse_iso_ms(end_time) if end_time else None
    if marker_mode in ("time_range", "selected") and chart_positions:
        win_start, win_end = compute_chart_window_ms(
            chart_positions, interval, start_ms=start_ms, end_ms=end_ms
        )
    elif marker_mode == "time_range" and (start_ms or end_ms):
        win_start, win_end = compute_chart_window_ms(
            [], interval, start_ms=start_ms, end_ms=end_ms
        )
    else:
        win_start, win_end = None, None

    try:
        if win_start is not None or win_end is not None:
            candles, source = load_candles(
                inst, interval, limit=0, start_ms=win_start, end_ms=win_end
            )
        else:
            candles, source = load_candles(inst, interval, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    markers_raw = build_markers(chart_positions if chart_positions else [], inst)
    if marker_mode == "all":
        markers_raw = build_markers([_position_history_to_dict(p) for p in positions_api], inst)

    visible_positions = chart_positions if marker_mode != "all" else [_position_history_to_dict(p) for p in positions_api]
    total_pnl = sum(float(p.get("pnl", 0)) for p in visible_positions)

    return ChartReviewResponse(
        symbol=inst,
        interval=interval,
        data_source=source,
        candles=[
            ChartCandle(
                time=c.time, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume
            )
            for c in candles
        ],
        markers=[
            ChartMarker(
                position_id=m.position_id,
                marker_type=m.marker_type,
                time=m.time,
                price=m.price,
                side=m.side,
                pnl=m.pnl,
                leverage=m.leverage,
                close_type=m.close_type,
                label=m.label,
            )
            for m in markers_raw
        ],
        positions=[PositionHistory(**p) for p in visible_positions] if marker_mode != "all" else positions_api,
        total_pnl=total_pnl,
    )


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
    """启动时加载 .env 并记录。"""
    _load_dotenv()
    _add_alert("INFO", "api_started", "FastAPI backend started")


# ================================================================== #
# 前端静态文件（生产构建：frontend/dist，单端口 8000 访问）
# ================================================================== #

if (FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="assets",
    )


@app.get("/")
def serve_frontend_index():
    """SPA 入口。"""
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise HTTPException(
            status_code=503,
            detail="前端未构建。请运行: cd frontend && npm run build",
        )
    return FileResponse(index)


@app.get("/{spa_path:path}")
def serve_frontend_spa(spa_path: str):
    """React Router 路径回退到 index.html。"""
    if spa_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    # 静态资源直出
    file_path = FRONTEND_DIST / spa_path
    if file_path.is_file():
        return FileResponse(file_path)
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise HTTPException(status_code=503, detail="前端未构建")
    return FileResponse(index)
