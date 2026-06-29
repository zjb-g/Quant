# BollingerBreakoutStrategy —— 布林带突破策略
#
# 决策依据：
#   - 时间框架 15m（ADR-002）
#   - 双向持仓 can_short=True（ADR-003）
#   - 杠杆 5x（ADR-003）
#
# 策略逻辑：
#   1. 价格突破布林带上轨 → 趋势加速做多
#   2. 价格跌破布林带下轨 → 趋势加速做空
#   3. 布林带宽度过滤（带宽过窄时不进场，避免假突破）
#   4. 参数全部可配置

from datetime import datetime

import pandas as pd
import talib.abstract as ta

from freqtrade.strategy import DecimalParameter, IStrategy


class BollingerBreakoutStrategy(IStrategy):
    """布林带突破策略。"""

    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True

    minimal_roi = {
        "0": 0.05,
        "45": 0.025,
        "90": 0.01,
        "150": 0.0,
    }

    stoploss = -0.035
    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True
    max_leverage = 5.0

    # 布林带参数
    bb_period = DecimalParameter(15, 30, default=20, space="buy", optimize=True)
    bb_std = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy", optimize=True)

    # 布林带宽度下限（避免假突破）：带宽 = (上轨-下轨)/中轨
    min_bandwidth = DecimalParameter(0.005, 0.05, default=0.02, decimals=4, space="buy", optimize=True)

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, side, **kwargs):
        return min(5.0, max_leverage)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 布林带：返回 upperband, middleband, lowerband
        upper, middle, lower = ta.BBANDS(
            dataframe["close"],
            timeperiod=int(self.bb_period.value),
            nbdevup=float(self.bb_std.value),
            nbdevdn=float(self.bb_std.value),
        )
        dataframe["bb_upper"] = upper
        dataframe["bb_middle"] = middle
        dataframe["bb_lower"] = lower
        # 布林带宽度
        dataframe["bb_bandwidth"] = (upper - lower) / middle
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 做多：收盘价突破上轨 + 带宽足够
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["bb_upper"])
                & (dataframe["close"].shift(1) <= dataframe["bb_upper"].shift(1))
                & (dataframe["bb_bandwidth"] > self.min_bandwidth.value)
            ),
            "enter_long",
        ] = 1

        # 做空：收盘价跌破下轨 + 带宽足够
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["bb_lower"])
                & (dataframe["close"].shift(1) >= dataframe["bb_lower"].shift(1))
                & (dataframe["bb_bandwidth"] > self.min_bandwidth.value)
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 多头退出：回到中轨下方
        dataframe.loc[
            (dataframe["close"] < dataframe["bb_middle"]),
            "exit_long",
        ] = 1

        # 空头退出：回到中轨上方
        dataframe.loc[
            (dataframe["close"] > dataframe["bb_middle"]),
            "exit_short",
        ] = 1

        return dataframe
