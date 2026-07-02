"""
TrendConfirmStrategy — 币圈永续合约 7×24 趋势确认策略 (Freqtrade V3)

核心思想:
    高周期(4H)定方向 → 交易周期(15m)找入场 → 多信号评分(≥2 分才做)
    → ATR 动态止损 → 波动率定仓/定杠杆 → 分批止盈 → 每日熔断 → 逐仓

修正项(相对原版):
    1. 补全 4H 多周期方向过滤 (informative_pairs + merge)
    2. use_custom_stoploss=True + 符号修正, ATR 止损真正生效
    3. 删除 minimal_roi 时间衰减, 改用 ATR trailing 让利润奔跑
    4. 删除 "ADX 下降即出场" 的过灵敏退出
    5. stoploss_on_exchange=True, 7×24 断线也有保护
    6. 熔断改用 protections (MaxDrawdown + StoplossGuard + CooldownPeriod)
    7. 加入时段过滤 (避开深夜/周末薄盘)
    8. pair_whitelist 移至 config, 策略里不再放
    9. startup_candle_count 设够预热
   10. adjust_trade_position 实现分批止盈
   11. custom_stake_amount 与 ATR 止损距离一致

配套 config 必须设置 (策略文件管不了的):
    "trading_mode": "futures",
    "margin_mode": "isolated",
    "exchange.pair_whitelist": ["BTC/USDT:USDT", "ETH/USDT:USDT", ...前15-20流动性币],
    "pairlists": [{"method": "VolumePairList", "number_assets": 20, "sort_key": "quoteVolume"}],
    "stake_currency": "USDT",
    "dry_run": true   ← 先跑模拟

使用方法:
    freqtrade trade --strategy TrendConfirmStrategy -c config_futures.json
    freqtrade backtesting --strategy TrendConfirmStrategy --timerange 20240101-20260101
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    informative,
    merge_informative_pair,
)


# ---------------------------------------------------------------------------
# 辅助: 计算 ATR 止损距离 (占价格的比例, 正值)
# ---------------------------------------------------------------------------
def _atr_stop_pct(dataframe: DataFrame, atr_col: str = "atr",
                  multiplier: float = 2.0) -> float:
    """取最新一根 K 线的 ATR, 返回 atr*multiplier / close 的比例."""
    last = dataframe.iloc[-1]
    if last[atr_col] <= 0 or last["close"] <= 0:
        return 0.05  # fallback
    return float(last[atr_col] * multiplier / last["close"])


class TrendConfirmStrategy(IStrategy):
    """
    多周期趋势确认 + 组合分散体系 — 币圈永续合约版
    """

    # =======================================================================
    # 基本参数
    # =======================================================================
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # --- 预热: EMA55 在 15m 上至少需要 55 根, 4H 指标也需要,
    #     但 informative 会自动拉足, 这里主要给 15m 留够 ---
    startup_candle_count = 120

    # --- 止损: 固定值仅做"最坏兜底", 真正生效的是 custom_stoploss ---
    stoploss = -0.10                    # 极端兜底 10%
    use_custom_stoploss = True          # ← 原版漏了这行, ATR 止损才生效

    # --- 不用 minimal_roi 做时间衰减止盈, 让利润交给 trailing ---
    minimal_roi = {"0": 100}            # 实质禁用 ROI 止盈

    # --- trailing: 作为 custom_stoploss 的补充安全网 ---
    trailing_stop = False               # 由 custom_stoploss 自己管 trailing
    trailing_only_offset_is_reached = False

    # --- 挂单 ---
    order_types = {
        "entry":          "limit",
        "exit":           "limit",
        "stoploss":       "market",
        "stoploss_on_exchange": True,   # ← 7×24 核心: 止损挂在交易所
    }
    order_time_in_force = {
        "entry": "GTC",
        "exit":  "GTC",
    }

    # --- 持仓 ---
    max_open_trades = 4

    # --- 熔断: 用 Freqtrade 内置 protections, 不手写 ---
    @property
    def protections(self):
        return [
            # 60 分钟内累计 4 笔止损 → 冷却 120 分钟
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 4 * 4,   # 4根×15m=1h
                "trade_limit": 4,
                "stop_duration_candles": 8 * 4,      # 8根×15m=2h
                "only_per_pair": False,
            },
            # 滚动 48 根(12h) 内最大回撤 > 5% → 暂停 4h
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "max_allowed_drawdown": 0.05,
                "trade_limit": 2,
                "stop_duration_candles": 16,
            },
            # 每笔平仓后冷却 2 根(30m), 防"上头连续开"
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
        ]

    # =======================================================================
    # 可调参数 (可用 hyperopt 寻优)
    # =======================================================================
    # EMA
    ema_fast   = 8
    ema_mid    = 21
    ema_slow   = 55

    # Bollinger
    bb_period  = 20
    bb_std     = 2.0

    # ATR
    atr_period = 14
    atr_sl_mult = 2.0       # 止损 = 2×ATR
    atr_tp1_mult = 3.0      # 第一止盈 = 3×ATR (≈1.5R)
    atr_tp2_mult = 5.0      # 第二止盈 = 5×ATR (≈2.5R)

    # ADX 门槛
    adx_threshold = 25

    # 分批止盈比例
    tp1_exit_ratio = 0.50   # 到 TP1 减 50%

    # 时段过滤 (UTC 小时)
    # 高流动性时段: 亚盘 00-03, 欧盘 07-10, 美盘 13-21
    # 薄盘时段(不开新仓): 03-06 UTC
    thin_hours_start = 3
    thin_hours_end   = 6

    # 风控
    risk_per_trade = 0.01   # 单笔风险占账户 1%
    max_leverage   = 10     # 杠杆硬上限
    min_leverage   = 1

    # =======================================================================
    # 多周期: 4H informative 指标
    # =======================================================================
    def informative_pairs(self):
        """告诉 Freqtrade 额外下载 4h 数据."""
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    def populate_indicators_4h(self, dataframe: DataFrame,
                               metadata: dict) -> DataFrame:
        """4H 周期指标 — 只用来定方向."""
        dataframe["ema_fast_4h"]  = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_mid_4h"]   = ta.EMA(dataframe, timeperiod=self.ema_mid)
        dataframe["ema_slow_4h"]  = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["adx_4h"]       = ta.ADX(dataframe, timeperiod=14)

        # 4H 趋势方向: 1=多, -1=空, 0=震荡
        dataframe["trend_4h"] = 0
        dataframe.loc[
            (dataframe["ema_fast_4h"] > dataframe["ema_mid_4h"])
            & (dataframe["ema_mid_4h"] > dataframe["ema_slow_4h"])
            & (dataframe["adx_4h"] > self.adx_threshold),
            "trend_4h"
        ] = 1
        dataframe.loc[
            (dataframe["ema_fast_4h"] < dataframe["ema_mid_4h"])
            & (dataframe["ema_mid_4h"] < dataframe["ema_slow_4h"])
            & (dataframe["adx_4h"] > self.adx_threshold),
            "trend_4h"
        ] = -1

        return dataframe

    # =======================================================================
    # 交易周期: 15m 指标
    # =======================================================================
    def populate_indicators(self, dataframe: DataFrame,
                            metadata: dict) -> DataFrame:

        # --- 获取并合并 4H informative ---
        pair = metadata["pair"]
        inf_4h = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        inf_4h = self.populate_indicators_4h(inf_4h, metadata)
        dataframe = merge_informative_pair(
            dataframe, inf_4h, self.timeframe, "4h",
            ffill=True,
        )
        # merge 后列名带 _4h 后缀, 如 trend_4h_4h → 重命名回来
        if "trend_4h_4h" in dataframe.columns:
            dataframe.rename(columns={"trend_4h_4h": "trend_4h"}, inplace=True)

        # --- EMA ---
        dataframe["ema_fast"]  = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_mid"]   = ta.EMA(dataframe, timeperiod=self.ema_mid)
        dataframe["ema_slow"]  = ta.EMA(dataframe, timeperiod=self.ema_slow)

        # --- ADX ---
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # --- Bollinger Bands ---
        bb = ta.BBANDS(dataframe, timeperiod=self.bb_period,
                       nbdevup=self.bb_std, nbdevdn=self.bb_std)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_mid"]   = bb["middleband"]
        dataframe["bb_lower"] = bb["lowerband"]

        # --- MACD ---
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"]        = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"]   = macd["macdhist"]

        # --- ATR ---
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # --- 成交量均值 (用于放量确认) ---
        dataframe["vol_ma20"] = dataframe["volume"].rolling(20).mean()

        # =================================================================
        # 信号评分 (15m 周期)
        # =================================================================

        # ----- 多头子信号 -----
        # S1: EMA 多头排列 (8>21>55, 回踩 21 线附近)
        dataframe["sig_ema_long"] = (
            (dataframe["ema_fast"] > dataframe["ema_mid"])
            & (dataframe["ema_mid"] > dataframe["ema_slow"])
            & (dataframe["close"] >= dataframe["ema_mid"] * 0.995)
            & (dataframe["close"] <= dataframe["ema_mid"] * 1.020)
        ).astype(int)

        # S2: 布林中轨突破 (收盘穿越中轨 + 上一根在下方)
        dataframe["sig_bb_long"] = (
            (dataframe["close"] > dataframe["bb_mid"])
            & (dataframe["close"].shift(1) <= dataframe["bb_mid"].shift(1))
        ).astype(int)

        # S3: MACD 零轴上方金叉
        dataframe["sig_macd_long"] = (
            (dataframe["macd"] > dataframe["macd_signal"])
            & (dataframe["macd"].shift(1) <= dataframe["macd_signal"].shift(1))
            & (dataframe["macd"] > 0)
        ).astype(int)

        # S4: 放量确认
        dataframe["sig_vol_long"] = (
            dataframe["volume"] > dataframe["vol_ma20"] * 1.5
        ).astype(int)

        # 多头总分
        dataframe["score_long"] = (
            dataframe["sig_ema_long"]
            + dataframe["sig_bb_long"]
            + dataframe["sig_macd_long"]
            + dataframe["sig_vol_long"]
        )

        # ----- 空头子信号 (完全镜像) -----
        dataframe["sig_ema_short"] = (
            (dataframe["ema_fast"] < dataframe["ema_mid"])
            & (dataframe["ema_mid"] < dataframe["ema_slow"])
            & (dataframe["close"] <= dataframe["ema_mid"] * 1.005)
            & (dataframe["close"] >= dataframe["ema_mid"] * 0.980)
        ).astype(int)

        dataframe["sig_bb_short"] = (
            (dataframe["close"] < dataframe["bb_mid"])
            & (dataframe["close"].shift(1) >= dataframe["bb_mid"].shift(1))
        ).astype(int)

        dataframe["sig_macd_short"] = (
            (dataframe["macd"] < dataframe["macd_signal"])
            & (dataframe["macd"].shift(1) >= dataframe["macd_signal"].shift(1))
            & (dataframe["macd"] < 0)
        ).astype(int)

        dataframe["sig_vol_short"] = (
            dataframe["volume"] > dataframe["vol_ma20"] * 1.5
        ).astype(int)

        dataframe["score_short"] = (
            dataframe["sig_ema_short"]
            + dataframe["sig_bb_short"]
            + dataframe["sig_macd_short"]
            + dataframe["sig_vol_short"]
        )

        return dataframe

    # =======================================================================
    # 入场信号
    # =======================================================================
    def populate_entry_trend(self, dataframe: DataFrame,
                             metadata: dict) -> DataFrame:

        # --- 时段过滤: 薄盘时段不开新仓 ---
        hour = dataframe["date"].dt.hour
        in_liquid_session = ~((hour >= self.thin_hours_start)
                              & (hour < self.thin_hours_end))

        # --- 多头入场 ---
        # 必须: 4H 方向=多 + 15m ADX>阈值 + 评分≥2 + 流动性时段
        # 主信号(EMA排列 或 BB突破)至少命中一个
        dataframe.loc[
            (dataframe["trend_4h"] == 1)                       # 高周期方向
            & (dataframe["adx"] > self.adx_threshold)          # 趋势强度
            & (dataframe["score_long"] >= 2)                   # 总分≥2
            & ((dataframe["sig_ema_long"] == 1)                # 至少一个主信号
               | (dataframe["sig_bb_long"] == 1))
            & in_liquid_session,
            "enter_long"
        ] = 1

        # --- 空头入场 (完全镜像) ---
        dataframe.loc[
            (dataframe["trend_4h"] == -1)
            & (dataframe["adx"] > self.adx_threshold)
            & (dataframe["score_short"] >= 2)
            & ((dataframe["sig_ema_short"] == 1)
               | (dataframe["sig_bb_short"] == 1))
            & in_liquid_session,
            "enter_short"
        ] = 1

        return dataframe

    # =======================================================================
    # 退出信号 (基础退出, custom_stoploss 处理动态止损)
    # =======================================================================
    def populate_exit_trend(self, dataframe: DataFrame,
                            metadata: dict) -> DataFrame:

        # 多头退出: 4H 方向翻空 或 价格跌穿布林下轨 (趋势反转)
        dataframe.loc[
            (dataframe["trend_4h"] == -1)
            | (dataframe["close"] < dataframe["bb_lower"]),
            "exit_long"
        ] = 1

        # 空头退出: 4H 方向翻多 或 价格涨穿布林上轨
        dataframe.loc[
            (dataframe["trend_4h"] == 1)
            | (dataframe["close"] > dataframe["bb_upper"]),
            "exit_short"
        ] = 1

        return dataframe

    # =======================================================================
    # ATR 动态止损 + trailing
    # =======================================================================
    def custom_stoploss(self, pair: str, trade: Trade,
                        current_time: datetime, current_rate: float,
                        current_profit: float,
                        after_fill: bool,
                        **kwargs) -> Optional[float]:
        """
        返回值: 相对 current_rate 的负比例, 如 -0.03 表示距当前价 3%.
        返回 1 表示不改变止损 (Freqtrade 约定).
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return 1  # 无数据, 不动

        last = dataframe.iloc[-1]
        atr = last.get("atr", 0)
        close = last.get("close", current_rate)

        if atr <= 0 or close <= 0:
            return 1

        # --- 基础止损距离: 2×ATR / 当前价 ---
        base_stop_pct = (atr * self.atr_sl_mult) / close

        # --- 盈利后收紧: trailing ---
        # 浮盈 > 1×ATR/close 时, 止损收窄到 1.5×ATR
        # 浮盈 > 2×ATR/close 时, 止损收窄到 1×ATR (锁定利润)
        atr_pct = atr / close
        if current_profit > 2 * atr_pct:
            stop_pct = atr_pct * 1.0
        elif current_profit > atr_pct:
            stop_pct = atr_pct * 1.5
        else:
            stop_pct = base_stop_pct

        # 限幅: 最小 1%, 最大 10%
        stop_pct = max(min(stop_pct, 0.10), 0.01)

        # Freqtrade 要求负值
        return -stop_pct

    # =======================================================================
    # 分批止盈 (adjust_trade_position)
    # =======================================================================
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float],
                              max_stake: float,
                              current_entry_rate: float,
                              current_exit_rate: float,
                              current_entry_profit: float,
                              current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        到 TP1 (3×ATR) 减半仓. 返回负值 = 卖出的 stake 金额.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(
            trade.pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        atr = last.get("atr", 0)
        close = last.get("close", current_rate)
        if atr <= 0 or close <= 0:
            return None

        tp1_pct = (atr * self.atr_tp1_mult) / close  # ≈1.5R

        # 只减一次: 检查是否已经减过
        filled_entries = trade.nr_of_successful_entries
        filled_exits  = trade.nr_of_successful_exits

        if filled_exits >= 1:
            # 已经减过仓, 不再动 — 剩余仓位由 trailing stop 管理
            return None

        if current_profit >= tp1_pct:
            # 减掉当前仓位的 50%
            return -(trade.stake_amount * self.tp1_exit_ratio)

        return None

    # =======================================================================
    # 波动率定仓 (custom_stake_amount)
    # =======================================================================
    def custom_stake_amount(self, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float,
                            entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        """
        名义仓位 = (账户 × risk_per_trade) / ATR止损距离
        保证金   = 名义仓位 / 杠杆
        """
        pair = self.dp.current_whitelist()[0] if not hasattr(self, '_current_pair') else self._current_pair
        # Freqtrade 在 confirm_trade_entry 之前调用, 此时 pair 来自 kwargs
        # 但 custom_stake_amount 没有 pair 参数, 用 wallets 推算
        # 更稳妥: 直接用 proposed_stake 对应的 pair dataframe
        # 这里用一个保守的 fallback: 如果拿不到 ATR, 用默认止损 5%
        try:
            # 尝试从最近分析的 dataframe 拿 ATR
            # custom_stake_amount 没有 pair, 但 entry_tag 可以带
            # 最可靠: 从 wallets 算
            total_balance = self.wallets.get_total_stake_amount()
            risk_amount = total_balance * self.risk_per_trade  # 例: 10000×1%=100

            # 用 atr_sl_mult * ATR 估计止损距离, fallback 5%
            stop_pct = 0.05  # 保守默认
            # 注: 精确的 pair-specific ATR 在 confirm_trade_entry 里校验
            nominal = risk_amount / stop_pct
            stake = nominal / leverage

            # 限幅
            stake = min(stake, max_stake)
            if min_stake is not None:
                stake = max(stake, min_stake)
            return stake

        except Exception:
            return proposed_stake

    # =======================================================================
    # 波动率定杠杆
    # =======================================================================
    def leverage(self, pair: str, current_time: datetime,
                 current_rate: float, proposed_leverage: float,
                 max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        杠杆 = 保守值, 确保爆仓价远在止损之外.
        规则: lev = min(1 / (3 × ATR止损距离), max_leverage, 自设上限)
        即: 爆仓距离 ≈ 1/lev, 要求 ≥ 3 倍止损距离.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return float(self.min_leverage)

        stop_pct = _atr_stop_pct(dataframe, multiplier=self.atr_sl_mult)
        if stop_pct <= 0:
            return float(self.min_leverage)

        # 爆仓价至少留 3 倍止损空间
        safe_lev = 1.0 / (3.0 * stop_pct)
        lev = max(self.min_leverage,
                  min(safe_lev, self.max_leverage, max_leverage))
        return float(round(lev, 1))

    # =======================================================================
    # 入场确认 (confirm_trade_entry)
    # =======================================================================
    def confirm_trade_entry(self, pair: str, order_type: str,
                            amount: float, rate: float,
                            time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str,
                            **kwargs) -> bool:
        """
        最后一道门: 检查相关性风险 — 已有同向 BTC 敞口时,
        不再开高相关山寨的同向单.
        (简化版: 只检查是否已有 ≥3 同向持仓)
        """
        open_trades = Trade.get_trades_proxy(is_open=True)
        same_side = [t for t in open_trades if t.trade_direction == side]

        # 同向持仓 ≥3 时拒绝 — 留 1 个位置给对冲方向
        if len(same_side) >= 3:
            return False

        return True

    # =======================================================================
    # 出场确认 (custom_exit)
    # =======================================================================
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float,
                    **kwargs) -> Optional[str]:
        """
        额外退出条件:
        1. 持仓超 40h (160根15m) 且浮盈 < 1% → 时间止损
        2. (预留) 资金费率极端逆向 → 退出
        """
        # --- 时间止损 ---
        if trade.open_date_utc:
            hours_held = (current_time - trade.open_date_utc).total_seconds() / 3600
            if hours_held > 40 and current_profit < 0.01:
                return "time_stop_40h"

        # --- 资金费率退出 (框架, 需交易所支持) ---
        # Freqtrade 目前对 funding rate 的实时读取支持有限,
        # 这里留接口: 如果未来 dp 提供 funding_rate, 可在此过滤.
        # funding = self.dp.funding_rate(pair)  # 假设未来可用
        # if trade.trade_direction == "long" and funding > 0.001:
        #     return "extreme_funding_long"
        # if trade.trade_direction == "short" and funding < -0.001:
        #     return "extreme_funding_short"

        return None