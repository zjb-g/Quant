# FundingRateTrendStrategy —— 趋势 + ATR + 资金费过滤策略（T1.3）
#
# 决策依据：
#   - 时间框架 15m（ADR-002）
#   - 双向持仓 can_short=True（ADR-003）
#   - 杠杆 5x（ADR-003），通过 leverage() 返回
#   - 资金费结算频率 8h（ADR-006）
#
# 策略逻辑：
#   1. EMA20/EMA50 判断趋势方向
#   2. ATR 过滤极端波动（ATR 占价格比例超过阈值时不进场）
#   3. 资金费率过滤过高持仓成本（资金费率绝对值超过阈值时不进场）
#   4. 支持 long/short
#   5. 参数全部可配置
#
# 信号说明：
#   enter_long  : EMA20 > EMA50（趋势向上）且 ATR 适中且资金费率可接受
#   enter_short : EMA20 < EMA50（趋势向下）且 ATR 适中且资金费率可接受
#   exit_long   : EMA20 < EMA50（趋势反转）
#   exit_short  : EMA20 > EMA50（趋势反转）

from datetime import datetime

import pandas as pd
import talib.abstract as ta

from freqtrade.strategy import DecimalParameter, IStrategy


class FundingRateTrendStrategy(IStrategy):
    """EMA 趋势 + ATR 过滤 + 资金费率过滤。"""

    INTERFACE_VERSION = 3

    # 策略主时间框架（决策 ADR-002）
    timeframe = "15m"

    # 双向持仓支持做空（决策 ADR-003）
    can_short = True

    # 阶梯止盈
    minimal_roi = {
        "0": 0.06,
        "45": 0.03,
        "90": 0.01,
        "180": 0.0,
    }

    # 固定止损 4%
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # 杠杆上限（决策 ADR-003），实际由 RiskManager 进一步约束
    max_leverage = 5.0

    # ---- 可配置参数 ----

    # EMA 周期
    ema_fast = DecimalParameter(10, 30, default=20, space="buy", optimize=True)
    ema_slow = DecimalParameter(40, 60, default=50, space="buy", optimize=True)

    # ATR 过滤：ATR 占价格比例上限（超过则波动过大，不进场）
    atr_period = DecimalParameter(10, 20, default=14, space="buy", optimize=False)
    max_atr_pct = DecimalParameter(0.005, 0.05, default=0.02, decimals=4, space="buy", optimize=True)

    # 资金费率过滤：资金费率绝对值上限（超过则持仓成本过高，不进场）
    # OKX 每 8h 结算一次，年化 0.01%*3*365=10.95%
    max_funding_rate = DecimalParameter(0.0001, 0.002, default=0.0005, decimals=6, space="buy", optimize=True)

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
        """计算 EMA、ATR、资金费率。"""
        # EMA 趋势指标
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=int(self.ema_fast.value))
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=int(self.ema_slow.value))

        # ATR 波动率指标
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period.value))
        # ATR 占价格比例（过滤极端波动）
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # 资金费率：从 Freqtrade 的 funding_rate 数据列获取
        # 回测时 Freqtrade 会注入 funding_rate 列；dry-run/live 时需通过 informative 或自定义获取
        # 这里先使用列（如果存在），不存在则默认 0
        if "funding_rate" not in dataframe.columns:
            dataframe["funding_rate"] = 0.0

        # 趋势方向：1=上升，-1=下降，0=横盘
        dataframe["trend"] = 0
        dataframe.loc[dataframe["ema_fast"] > dataframe["ema_slow"], "trend"] = 1
        dataframe.loc[dataframe["ema_fast"] < dataframe["ema_slow"], "trend"] = -1

        return dataframe

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """做多：趋势向上 + ATR 适中 + 资金费率可接受。"""
        # 做多条件
        long_condition = (
            (dataframe["trend"] == 1)  # EMA20 > EMA50，趋势向上
            & (dataframe["ema_fast"] > dataframe["ema_fast"].shift(1))  # EMA 加速
            & (dataframe["atr_pct"] < self.max_atr_pct.value)  # 波动率适中
            & (dataframe["funding_rate"] < self.max_funding_rate.value)  # 资金费率可接受
        )
        dataframe.loc[long_condition, "enter_long"] = 1

        # 做空条件
        short_condition = (
            (dataframe["trend"] == -1)  # EMA20 < EMA50，趋势向下
            & (dataframe["ema_fast"] < dataframe["ema_fast"].shift(1))  # EMA 加速下行
            & (dataframe["atr_pct"] < self.max_atr_pct.value)  # 波动率适中
            & (dataframe["funding_rate"] > -self.max_funding_rate.value)  # 资金费率可接受（做空时正费率有利）
        )
        dataframe.loc[short_condition, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """趋势反转时退出。"""
        # 多头退出：趋势反转向下
        dataframe.loc[
            (dataframe["trend"] == -1),
            "exit_long",
        ] = 1

        # 空头退出：趋势反转向上
        dataframe.loc[
            (dataframe["trend"] == 1),
            "exit_short",
        ] = 1

        return dataframe
