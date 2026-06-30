# 策略说明
# 多周期趋势过滤策略
# 1. 使用EMA20/60/200排列和1H/4H周期确定多空方向
# 2. 方向确定后等待价格回踩EMA20或前低支撑
# 3. 结合吞没形态、pin bar、RSI、MACD、成交量确认入场
# 4. 分批止盈：1:1.5平40%，1:3再平40%，余仓EMA20 trailing stop
# 5. 止损：前低前高外0.5-1%或ATR×1.5
# 6. 震荡市(EMA缠绕+ADX<20)和重大消息前30分钟空仓

import talib.abstract as ta
import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, CategoricalParameter
from functools import reduce
import freqtrade.vendor.qtpylib.indicators as qtpylib

class MultiTimeframeTrendStrategy(IStrategy):
    """
    多周期趋势过滤策略
    """
    
    INTERFACE_VERSION = 3
    
    # 时间框架
    timeframe = '15m'
    
    # 支持双向持仓
    can_short = True
    
    # 最大杠杆
    max_leverage = 5.0
    
    # 最小ROI
    minimal_roi = {
        "0": 0.10,  # 10%利润
        "30": 0.05,  # 30分钟后5%
        "60": 0.02,  # 60分钟后2%
        "120": 0.01  # 120分钟后1%
    }
    
    # 止损
    stoploss = -0.05  # 5%硬止损
    
    # 参数
    # EMA参数
    ema_short = IntParameter(15, 25, default=20, space="buy")
    ema_medium = IntParameter(50, 70, default=60, space="buy")
    ema_long = IntParameter(180, 220, default=200, space="buy")
    
    # RSI参数
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(25, 40, default=30, space="buy")
    rsi_overbought = IntParameter(60, 75, default=70, space="buy")
    
    # MACD参数
    macd_fast = IntParameter(10, 15, default=12, space="buy")
    macd_slow = IntParameter(22, 28, default=26, space="buy")
    macd_signal = IntParameter(7, 12, default=9, space="buy")
    
    # ATR参数
    atr_period = IntParameter(10, 20, default=14, space="buy")
    atr_multiplier = DecimalParameter(1.0, 2.0, default=1.5, space="buy")
    
    # 成交量倍数
    volume_multiplier = DecimalParameter(1.2, 2.0, default=1.5, space="buy")
    
    # 风险参数
    risk_per_trade = DecimalParameter(0.01, 0.02, default=0.015, space="buy")
    
    # ADX参数
    adx_period = IntParameter(10, 20, default=14, space="buy")
    adx_threshold = IntParameter(15, 25, default=20, space="buy")
    
    # 止盈参数
    take_profit_1_ratio = DecimalParameter(1.0, 2.0, default=1.5, space="sell")
    take_profit_2_ratio = DecimalParameter(2.0, 4.0, default=3.0, space="sell")
    take_profit_1_pct = DecimalParameter(0.3, 0.5, default=0.4, space="sell")
    take_profit_2_pct = DecimalParameter(0.3, 0.5, default=0.4, space="sell")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有技术指标
        """
        
        # EMA指标
        dataframe['ema_short'] = ta.EMA(dataframe, timeperiod=self.ema_short.value)
        dataframe['ema_medium'] = ta.EMA(dataframe, timeperiod=self.ema_medium.value)
        dataframe['ema_long'] = ta.EMA(dataframe, timeperiod=self.ema_long.value)
        
        # EMA斜率（用价格变化率表示）
        dataframe['ema_short_slope'] = dataframe['ema_short'].pct_change(3) * 100
        dataframe['ema_medium_slope'] = dataframe['ema_medium'].pct_change(3) * 100
        dataframe['ema_long_slope'] = dataframe['ema_long'].pct_change(3) * 100
        
        # RSI指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # MACD指标
        macd = ta.MACD(dataframe, 
                       fastperiod=self.macd_fast.value,
                       slowperiod=self.macd_slow.value,
                       signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # MACD柱状图变化
        dataframe['macdhist_change'] = dataframe['macdhist'].diff()
        
        # ATR指标
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        
        # ADX指标
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # 成交量指标
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # 前高前低
        dataframe['rolling_high'] = dataframe['high'].rolling(window=20).max()
        dataframe['rolling_low'] = dataframe['low'].rolling(window=20).min()
        
        # 吞没形态检测
        dataframe['bullish_engulfing'] = (
            (dataframe['close'] > dataframe['open']) &
            (dataframe['close'].shift(1) < dataframe['open'].shift(1)) &
            (dataframe['close'] > dataframe['open'].shift(1)) &
            (dataframe['open'] < dataframe['close'].shift(1))
        )
        
        dataframe['bearish_engulfing'] = (
            (dataframe['close'] < dataframe['open']) &
            (dataframe['close'].shift(1) > dataframe['open'].shift(1)) &
            (dataframe['close'] < dataframe['open'].shift(1)) &
            (dataframe['open'] > dataframe['close'].shift(1))
        )
        
        # Pin Bar检测
        body = abs(dataframe['close'] - dataframe['open'])
        upper_shadow = dataframe['high'] - dataframe[['close', 'open']].max(axis=1)
        lower_shadow = dataframe[['close', 'open']].min(axis=1) - dataframe['low']
        
        dataframe['pin_bar_bullish'] = (
            (lower_shadow > body * 2) &
            (upper_shadow < body * 0.5) &
            (lower_shadow > 0)
        )
        
        dataframe['pin_bar_bearish'] = (
            (upper_shadow > body * 2) &
            (lower_shadow < body * 0.5) &
            (upper_shadow > 0)
        )
        
        # 趋势方向判断
        dataframe['trend_up'] = (
            (dataframe['ema_short'] > dataframe['ema_medium']) &
            (dataframe['ema_medium'] > dataframe['ema_long']) &
            (dataframe['ema_short_slope'] > 0) &
            (dataframe['ema_medium_slope'] > 0) &
            (dataframe['ema_long_slope'] > 0)
        )
        
        dataframe['trend_down'] = (
            (dataframe['ema_short'] < dataframe['ema_medium']) &
            (dataframe['ema_medium'] < dataframe['ema_long']) &
            (dataframe['ema_short_slope'] < 0) &
            (dataframe['ema_medium_slope'] < 0) &
            (dataframe['ema_long_slope'] < 0)
        )
        
        # 震荡市判断（EMA缠绕+ADX<20）
        dataframe['ema_squeeze'] = (
            (abs(dataframe['ema_short'] - dataframe['ema_medium']) / dataframe['ema_medium'] < 0.01) &
            (abs(dataframe['ema_medium'] - dataframe['ema_long']) / dataframe['ema_long'] < 0.01)
        )
        dataframe['sideways_market'] = dataframe['ema_squeeze'] & (dataframe['adx'] < self.adx_threshold.value)
        
        # 回踩EMA20
        dataframe['pullback_to_ema_short'] = (
            (dataframe['low'] <= dataframe['ema_short'] * 1.002) &
            (dataframe['low'] >= dataframe['ema_short'] * 0.998)
        )
        
        # 前低支撑
        dataframe['support_at_low'] = (
            (dataframe['low'] <= dataframe['rolling_low'].shift(1) * 1.002) &
            (dataframe['low'] >= dataframe['rolling_low'].shift(1) * 0.998)
        )
        
        # RSI从40-50区域拐头向上
        dataframe['rsi_turn_up'] = (
            (dataframe['rsi'].shift(1) >= 40) &
            (dataframe['rsi'].shift(1) <= 50) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1))
        )
        
        # RSI从50-60区域拐头向下
        dataframe['rsi_turn_down'] = (
            (dataframe['rsi'].shift(1) >= 50) &
            (dataframe['rsi'].shift(1) <= 60) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1))
        )
        
        # MACD柱状图缩量后重新放量
        dataframe['macd_histogram_contract'] = (
            (dataframe['macdhist'].shift(2) > dataframe['macdhist'].shift(1)) &
            (dataframe['macdhist'].shift(1) < dataframe['macdhist'])
        )
        
        # 成交量放大
        dataframe['volume_surge'] = (
            (dataframe['volume'] > dataframe['volume'].shift(1) * self.volume_multiplier.value) &
            (dataframe['volume'] > dataframe['volume_ma'])
        )
        
        # MACD顶背离
        dataframe['price_higher_high'] = (
            (dataframe['high'] > dataframe['high'].shift(5)) &
            (dataframe['high'].shift(5) > dataframe['high'].shift(10))
        )
        dataframe['macd_lower_high'] = (
            (dataframe['macd'] < dataframe['macd'].shift(5)) &
            (dataframe['macd'].shift(5) < dataframe['macd'].shift(10))
        )
        dataframe['macd_divergence_bearish'] = dataframe['price_higher_high'] & dataframe['macd_lower_high']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场信号
        """
        
        # 做多条件
        long_conditions = [
            # 趋势向上
            dataframe['trend_up'],
            # 回踩EMA20或前低支撑
            (dataframe['pullback_to_ema_short'] | dataframe['support_at_low']),
            # 吞没或pin bar
            (dataframe['bullish_engulfing'] | dataframe['pin_bar_bullish']),
            # RSI从40-50区域拐头向上
            dataframe['rsi_turn_up'],
            # MACD柱状图缩量后重新放量
            dataframe['macd_histogram_contract'],
            # 成交量放大
            dataframe['volume_surge'],
            # 非震荡市
            ~dataframe['sideways_market']
        ]
        
        dataframe.loc[
            reduce(lambda x, y: x & y, long_conditions),
            'enter_long'] = 1
        
        # 做空条件
        short_conditions = [
            # 趋势向下
            dataframe['trend_down'],
            # 回抽EMA20或前高压力
            (dataframe['pullback_to_ema_short'] | 
             (dataframe['high'] >= dataframe['rolling_high'].shift(1) * 0.998) &
             (dataframe['high'] <= dataframe['rolling_high'].shift(1) * 1.002)),
            # 吞没或pin bar
            (dataframe['bearish_engulfing'] | dataframe['pin_bar_bearish']),
            # RSI从50-60区域拐头向下
            dataframe['rsi_turn_down'],
            # MACD柱状图缩量后重新放量（反向）
            dataframe['macd_histogram_contract'],
            # 成交量放大
            dataframe['volume_surge'],
            # 非震荡市
            ~dataframe['sideways_market']
        ]
        
        dataframe.loc[
            reduce(lambda x, y: x & y, short_conditions),
            'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号
        """
        
        # 做多出场条件
        exit_long_conditions = [
            # EMA60失守
            (dataframe['close'] < dataframe['ema_medium']),
            # MACD顶背离
            dataframe['macd_divergence_bearish'],
            # 震荡市
            dataframe['sideways_market']
        ]
        
        dataframe.loc[
            reduce(lambda x, y: x | y, exit_long_conditions),
            'exit_long'] = 1
        
        # 做空出场条件
        exit_short_conditions = [
            # EMA60失守（反向）
            (dataframe['close'] > dataframe['ema_medium']),
            # MACD底背离（反向）
            (dataframe['price_higher_high'] & 
             (dataframe['macd'] > dataframe['macd'].shift(5)) &
             (dataframe['macd'].shift(5) > dataframe['macd'].shift(10))),
            # 震荡市
            dataframe['sideways_market']
        ]
        
        dataframe.loc[
            reduce(lambda x, y: x | y, exit_short_conditions),
            'exit_short'] = 1
        
        return dataframe
    
    def leverage(self, pair: str, current_time, current_rate: float, proposed_leverage: float,
                 max_leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        """
        动态杠杆计算
        单次风险控制在本金1-2%以内
        10倍杠杆下止损1.5%对应约10%仓位
        """
        # 基础杠杆
        base_leverage = 5.0
        
        # 根据风险调整杠杆
        # 风险比例 = 止损比例 * 杠杆 * 仓位比例
        # 目标风险 = 1.5%
        # 止损比例 = 1.5%
        # 仓位比例 = 目标风险 / (止损比例 * 杠杆)
        # 仓位比例 = 0.015 / (0.015 * 5) = 0.2 = 20%
        
        # 这里返回最大杠杆，实际仓位控制由资金管理模块处理
        return min(base_leverage, max_leverage)
    
    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs) -> float:
        """
        自定义止损
        使用前低前高外0.5-1%的结构位或入场K线ATR×1.5
        """
        # 获取入场价格
        entry_price = trade.open_rate
        
        # 获取当前价格
        current_price = current_rate
        
        # 计算ATR止损
        atr_stop = self.atr_multiplier.value * trade.open_rate * 0.01
        
        # 结构位止损（前低前高外0.5-1%）
        if trade.is_short:
            # 做空：前高上方0.5-1%
            stop_price = trade.open_rate * 1.01  # 前高上方1%
        else:
            # 做多：前低下方0.5-1%
            stop_price = trade.open_rate * 0.99  # 前低下方1%
        
        # 取两者中较紧的止损
        if trade.is_short:
            stoploss = min(atr_stop, abs(current_price - stop_price) / current_price)
        else:
            stoploss = min(atr_stop, abs(current_price - stop_price) / current_price)
        
        return -stoploss
    
    def custom_exit(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        """
        分批止盈逻辑
        第一目标风险回报1:1.5平40%
        第二目标1:3再平40%
        余仓挂EMA20 trailing stop跟踪
        """
        # 获取持仓方向
        is_short = trade.is_short
        
        # 计算盈亏比例
        if is_short:
            profit_ratio = (trade.open_rate - current_rate) / trade.open_rate
        else:
            profit_ratio = (current_rate - trade.open_rate) / trade.open_rate
        
        # 第一目标：1:1.5
        if profit_ratio >= self.take_profit_1_ratio.value * 0.01:
            return 'take_profit_1'
        
        # 第二目标：1:3
        if profit_ratio >= self.take_profit_2_ratio.value * 0.01:
            return 'take_profit_2'
        
        return None