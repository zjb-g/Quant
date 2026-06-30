# 策略说明
# 基于52周最高价逼近度因子的动量策略
# 因子 = 当前收盘价 / 过去52周最高价
# 当因子值接近1时买入（价格接近52周高点，动量强劲）
# 当因子值远离1时卖出（价格远离52周高点，动量减弱）

from datetime import datetime

import talib.abstract as ta
import pandas as pd
import numpy as np
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame

class FiftyTwoWeekHighApproachStrategy(IStrategy):
    """
    52周最高价逼近度策略
    
    核心逻辑：
    1. 计算当前收盘价与过去52周最高价的比值
    2. 比值越接近1，代表价格越接近52周高点，动量越强
    3. 比值低于阈值时，代表价格远离高点，动量减弱
    """
    
    INTERFACE_VERSION = 3
    
    # 使用15分钟时间框架
    timeframe = '15m'
    
    # 支持做空
    can_short = True
    
    # 最大杠杆
    max_leverage = 5.0
    
    # 最小ROI（年化收益率）
    minimal_roi = {
        "0": 0.10,      # 10% 收益
        "30": 0.05,     # 30分钟后5%
        "60": 0.02,     # 60分钟后2%
        "120": 0.01,    # 120分钟后1%
        "240": 0        # 240分钟后0%
    }
    
    # 止损
    stoploss = -0.05  # 5%止损
    
    # 参数优化空间
    # 买入阈值：因子值高于此值时买入（价格接近52周高点）
    buy_threshold = DecimalParameter(0.85, 0.99, default=0.95, space="buy")
    # 卖出阈值：因子值低于此值时卖出（价格远离52周高点）
    sell_threshold = DecimalParameter(0.50, 0.85, default=0.70, space="sell")
    # 52周周期（以15分钟K线计算，约52周*5天*24小时*4根/小时）
    lookback_period = IntParameter(24960, 24960, default=24960, space="buy")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算技术指标
        """
        # 计算52周最高价（滚动窗口最大值）
        # 注意：52周约等于24960根15分钟K线（52周 * 5天 * 24小时 * 4根/小时）
        dataframe['high_52w'] = dataframe['close'].rolling(window=self.lookback_period.value, min_periods=1).max()
        
        # 计算52周最高价逼近度因子
        # 因子 = 当前收盘价 / 过去52周最高价
        dataframe['approach_ratio'] = dataframe['close'] / dataframe['high_52w']
        
        # 计算因子变化率（用于辅助判断）
        dataframe['approach_ratio_change'] = dataframe['approach_ratio'].pct_change(periods=1)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义入场信号
        """
        # 做多信号：因子值高于买入阈值（价格接近52周高点，动量强劲）
        dataframe.loc[
            (
                (dataframe['approach_ratio'] > self.buy_threshold.value) &  # 因子值高于买入阈值
                (dataframe['volume'] > 0)  # 确保有成交量
            ),
            'enter_long'] = 1
        
        # 做空信号：因子值低于卖出阈值（价格远离52周高点，动量减弱）
        dataframe.loc[
            (
                (dataframe['approach_ratio'] < self.sell_threshold.value) &  # 因子值低于卖出阈值
                (dataframe['volume'] > 0)  # 确保有成交量
            ),
            'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义出场信号
        """
        # 多头出场：因子值跌破卖出阈值（动量减弱）
        dataframe.loc[
            (
                (dataframe['approach_ratio'] < self.sell_threshold.value) &  # 因子值低于卖出阈值
                (dataframe['volume'] > 0)  # 确保有成交量
            ),
            'exit_long'] = 1
        
        # 空头出场：因子值突破买入阈值（动量增强）
        dataframe.loc[
            (
                (dataframe['approach_ratio'] > self.buy_threshold.value) &  # 因子值高于买入阈值
                (dataframe['volume'] > 0)  # 确保有成交量
            ),
            'exit_short'] = 1
        
        return dataframe
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        计算杠杆倍数
        """
        # 使用最大杠杆，但不超过策略设定的最大杠杆
        return min(5.0, self.max_leverage)