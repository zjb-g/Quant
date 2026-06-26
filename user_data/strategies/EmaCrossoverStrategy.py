# EmaCrossoverStrategy —— 最小 EMA 交叉策略（T0.3）
#
# 决策依据：
#   - 时间框架 15m（ADR-002）
#   - 双向持仓 can_short=True，默认仅开多 enable_short=False
#   - 杠杆 5x（ADR-003），通过 leverage() 返回
#   - 不含复杂风控，风控由 quant_guard.risk.RiskManager 在执行层拦截
#
# 信号说明：
#   做多 enter_long : EMA20 由下而上穿越 EMA50
#   做空 enter_short: EMA20 由上而下穿越 EMA50（需 enable_short=True）
#   多头退出 exit_long : EMA20 跌破 EMA50
#   空头退出 exit_short: EMA20 突破 EMA50

from datetime import datetime

import pandas as pd
import talib.abstract as ta

from freqtrade.strategy import IStrategy, BooleanParameter


class EmaCrossoverStrategy(IStrategy):
    """EMA20/EMA50 交叉最小策略。"""

    INTERFACE_VERSION = 3

    # 策略主时间框架（决策 ADR-002）
    timeframe = "15m"

    # 双向持仓支持做空（决策 ADR-003）
    can_short = True

    # 阶梯止盈
    minimal_roi = {
        "0": 0.05,
        "30": 0.03,
        "60": 0.01,
        "120": 0.0,
    }

    # 固定止损 5%
    stoploss = -0.05
    trailing_stop = False

    # 默认仅做多；设为 True 后开启做空信号
    enable_short = BooleanParameter(
        default=False, space="strategy", optimize=False, load=True
    )

    # 杠杆上限（决策 ADR-003），实际由 RiskManager 进一步约束
    max_leverage = 5.0

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        side: str,
        **kwargs,
    ) -> float:
        """统一返回 5x 杠杆，不超过交易所允许上限。"""
        return min(5.0, max_leverage)

    def populate_indicators(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """计算 EMA20 / EMA50。"""
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """EMA20 上穿 EMA50 → 做多；下穿 → 做空（需 enable_short=True）。"""
        # 做多：EMA20 由下而上穿越 EMA50
        dataframe.loc[
            (
                (dataframe["ema20"] > dataframe["ema50"])
                & (dataframe["ema20"].shift(1) <= dataframe["ema50"].shift(1))
            ),
            "enter_long",
        ] = 1

        # 做空：EMA20 由上而下穿越 EMA50（默认关闭）
        if self.enable_short.value:
            dataframe.loc[
                (
                    (dataframe["ema20"] < dataframe["ema50"])
                    & (dataframe["ema20"].shift(1) >= dataframe["ema50"].shift(1))
                ),
                "enter_short",
            ] = 1

        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """多头：EMA20 跌破 EMA50 退出；空头：EMA20 突破 EMA50 退出。"""
        # 多头退出
        dataframe.loc[
            (dataframe["ema20"] < dataframe["ema50"]),
            "exit_long",
        ] = 1

        # 空头退出
        if self.enable_short.value:
            dataframe.loc[
                (dataframe["ema20"] > dataframe["ema50"]),
                "exit_short",
            ] = 1

        return dataframe
