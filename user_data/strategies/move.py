# 策略说明：
# 1. 在1分钟级别，检测连续三根K线实体逐渐变大后进场
# 2. 做多：止损线放在前一根K线的开盘价和收盘价的一半
# 3. 做多：如果当前K线收盘为盈利，则移动止损到该K线的开盘价
# 4. 做多：不断移动止损价直到价格跌破前一根K线的开盘价止盈卖出
# 5. 做空：逻辑相反（实体连续变大做空，止损/止盈规则反向）

import talib.abstract as ta
import pandas as pd
import numpy as np
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from functools import reduce

class ConsecutiveBodyExpansionStrategy(IStrategy):
    """
    连续K线实体放大策略
    """
    INTERFACE_VERSION = 3
    
    # 1分钟级别
    timeframe = '1m'
    
    # 支持双向持仓
    can_short = True
    
    # 最大杠杆
    max_leverage = 5.0
    
    # 最小ROI（默认不限制，由动态止损控制）
    minimal_roi = {
        "0": 0.01  # 最小盈利0.01%即允许退出（实际由止损逻辑控制）
    }
    
    # 初始止损（会被动态覆盖）
    stoploss = -0.05
    
    # 参数：连续实体放大K线数量
    consecutive_candles = IntParameter(2, 5, default=3, space="buy", optimize=True)
    
    # 参数：实体放大最小倍数
    body_ratio = DecimalParameter(1.1, 2.0, default=1.5, space="buy", optimize=True)
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算指标：
        - body_size: K线实体大小（|收盘-开盘|）
        - body_ratio_prev: 当前实体与前一根实体比值
        - body_expanding: 实体是否连续放大
        - prev_open: 前一根K线开盘价
        - prev_close: 前一根K线收盘价
        - prev_high: 前一根K线最高价
        - prev_low: 前一根K线最低价
        """
        # 计算K线实体大小
        dataframe['body_size'] = abs(dataframe['close'] - dataframe['open'])
        
        # 前一根实体大小
        dataframe['prev_body_size'] = dataframe['body_size'].shift(1)
        
        # 实体放大比例
        dataframe['body_ratio_val'] = dataframe['body_size'] / dataframe['prev_body_size'].replace(0, np.nan)
        
        # 判断实体是否放大（大于阈值）
        dataframe['body_expanding'] = dataframe['body_ratio_val'] > float(self.body_ratio.value)
        
        # 连续放大计数（向量化，避免 1m 全年数据逐行循环超时）
        dataframe['body_expand_count'] = (
            dataframe['body_expanding']
            .groupby((~dataframe['body_expanding']).cumsum())
            .cumsum()
            .astype(int)
        )
        
        # 前一根K线的开盘价、收盘价、最高价、最低价
        dataframe['prev_open'] = dataframe['open'].shift(1)
        dataframe['prev_close'] = dataframe['close'].shift(1)
        dataframe['prev_high'] = dataframe['high'].shift(1)
        dataframe['prev_low'] = dataframe['low'].shift(1)
        
        # 前两根K线的开盘价、收盘价
        dataframe['prev2_open'] = dataframe['open'].shift(2)
        dataframe['prev2_close'] = dataframe['close'].shift(2)
        
        # 前一根K线实体中点（用于初始止损）
        dataframe['prev_body_mid'] = (dataframe['prev_open'] + dataframe['prev_close']) / 2
        
        # 当前K线是否盈利（收盘价 > 开盘价 为盈利）
        dataframe['is_profitable'] = dataframe['close'] > dataframe['open']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        进场信号：
        - 做多：连续N根K线实体放大，且当前K线为阳线（收盘>开盘）
        - 做空：连续N根K线实体放大，且当前K线为阴线（收盘<开盘）
        """
        # 做多条件：连续实体放大达到阈值，且当前为阳线
        long_condition = (
            (dataframe['body_expand_count'] >= self.consecutive_candles.value) &
            (dataframe['close'] > dataframe['open'])  # 阳线
        )
        
        # 做空条件：连续实体放大达到阈值，且当前为阴线
        short_condition = (
            (dataframe['body_expand_count'] >= self.consecutive_candles.value) &
            (dataframe['close'] < dataframe['open'])  # 阴线
        )
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        dataframe.loc[short_condition, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号（由custom_stoploss动态控制，这里不设置固定出场）
        """
        # 出场由custom_stoploss和custom_exit动态控制
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态止损逻辑：
        - 做多：初始止损 = 前一根K线开盘价和收盘价的中点
        - 做多：如果当前K线收盘盈利，移动止损到该K线开盘价
        - 做多：不断移动止损，直到价格跌破前一根K线开盘价止盈
        - 做空：逻辑相反
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        if trade.is_short:
            initial_stop = (last_candle['prev_open'] + last_candle['prev_close']) / 2
            if last_candle['close'] < last_candle['open']:
                # 做空盈利：止损移到开盘价上方（返回负值表示相对 current_rate 的止损比例）
                return (last_candle['open'] - current_rate) / current_rate
            return (initial_stop - current_rate) / current_rate
        else:
            initial_stop = (last_candle['prev_open'] + last_candle['prev_close']) / 2
            if last_candle['close'] > last_candle['open']:
                return (last_candle['open'] - current_rate) / current_rate
            return (initial_stop - current_rate) / current_rate
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> bool:
        """
        自定义出场逻辑：
        - 做多：当价格跌破前一根K线的开盘价时止盈卖出
        - 做空：当价格突破前一根K线的开盘价时止盈买入
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        if trade.is_short:
            # 做空：价格突破前一根K线开盘价时止盈（买入平仓）
            if current_rate > last_candle['prev_open']:
                return True
        else:
            # 做多：价格跌破前一根K线开盘价时止盈（卖出平仓）
            if current_rate < last_candle['prev_open']:
                return True
        
        return False
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        杠杆设置：固定使用5倍杠杆
        """
        return min(5.0, self.max_leverage)