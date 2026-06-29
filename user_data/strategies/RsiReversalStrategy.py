# RsiReversalStrategy —— RSI 超买超卖反转策略
#
# 决策依据：
#   - 时间框架 15m（ADR-002）
#   - 双向持仓 can_short=True（ADR-003）
#   - 杠杆 5x（ADR-003）
#
# 策略逻辑：
#   1. RSI 低于 oversold 阈值 → 超卖反弹做多
#   2. RSI 高于 overbought 阈值 → 超买回落做空
#   3. 成交量放大过滤（避免低量假信号）
#   4. 参数全部可配置

from datetime import datetime

import pandas as pd
import talib.abstract as ta

from freqtrade.strategy import DecimalParameter, IStrategy


class RsiReversalStrategy(IStrategy):
    """RSI 超买超卖反转策略。"""

    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True

    minimal_roi = {
        "0": 0.04,
        "30": 0.02,
        "60": 0.01,
        "120": 0.0,
    }

    stoploss = -0.03
    trailing_stop = False
    max_leverage = 5.0

    # RSI 参数
    rsi_period = DecimalParameter(7, 21, default=14, space="buy", optimize=True)
    rsi_oversold = DecimalParameter(20, 40, default=30, space="buy", optimize=True)
    rsi_overbought = DecimalParameter(60, 80, default=70, space="buy", optimize=True)

    # 成交量过滤：当前成交量需大于 N 周期均量
    volume_factor = DecimalParameter(1.0, 2.0, default=1.2, decimals=1, space="buy", optimize=True)

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, side, **kwargs):
        return min(5.0, max_leverage)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))
        dataframe["volume_ma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 做多：RSI 从超卖区上穿 oversold 阈值 + 成交量放大
        dataframe.loc[
            (
                (dataframe["rsi"] > self.rsi_oversold.value)
                & (dataframe["rsi"].shift(1) <= self.rsi_oversold.value)
                & (dataframe["volume"] > dataframe["volume_ma"] * self.volume_factor.value)
            ),
            "enter_long",
        ] = 1

        # 做空：RSI 从超买区下穿 overbought 阈值 + 成交量放大
        dataframe.loc[
            (
                (dataframe["rsi"] < self.rsi_overbought.value)
                & (dataframe["rsi"].shift(1) >= self.rsi_overbought.value)
                & (dataframe["volume"] > dataframe["volume_ma"] * self.volume_factor.value)
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 多头退出：RSI 进入超买区
        dataframe.loc[
            (dataframe["rsi"] > self.rsi_overbought.value),
            "exit_long",
        ] = 1

        # 空头退出：RSI 进入超卖区
        dataframe.loc[
            (dataframe["rsi"] < self.rsi_oversold.value),
            "exit_short",
        ] = 1

        return dataframe
