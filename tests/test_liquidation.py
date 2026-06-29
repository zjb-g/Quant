"""tests/test_liquidation: 强平距离与强平模拟模块测试。"""

import pytest

from quant_guard.backtest.liquidation import (
    MarginMode,
    analyze_liquidation_risk,
    estimate_liquidation_price,
    liquidation_distance_pct,
    should_trigger_liquidation,
)
from quant_guard.exchange.models import Side


# ---------------------------------------------------------------------- #
# 强平价估算
# ---------------------------------------------------------------------- #
def test_long_liquidation_price():
    """多头强平价：entry * (1 - 1/lev + mmr)。"""
    # 60000, 5x, mmr=0.5% → 60000 * (1 - 0.2 + 0.005) = 60000 * 0.805 = 48300
    liq = estimate_liquidation_price(60000, 5, Side.LONG)
    assert liq == pytest.approx(48300.0)


def test_short_liquidation_price():
    """空头强平价：entry * (1 + 1/lev - mmr)。"""
    # 60000, 5x, mmr=0.5% → 60000 * (1 + 0.2 - 0.005) = 60000 * 1.195 = 71700
    liq = estimate_liquidation_price(60000, 5, Side.SHORT)
    assert liq == pytest.approx(71700.0)


def test_higher_leverage_closer_liquidation():
    """杠杆越高，强平价越接近开仓价。"""
    liq_5x = estimate_liquidation_price(60000, 5, Side.LONG)
    liq_10x = estimate_liquidation_price(60000, 10, Side.LONG)
    # 10x 强平价更接近 60000（更高）
    assert liq_10x > liq_5x


def test_lower_leverage_farther_liquidation():
    """杠杆越低，强平价越远离开仓价。"""
    liq_3x = estimate_liquidation_price(60000, 3, Side.LONG)
    liq_5x = estimate_liquidation_price(60000, 5, Side.LONG)
    # 3x 强平价更低（更远）
    assert liq_3x < liq_5x


def test_long_liq_below_entry():
    """多头强平价低于开仓价。"""
    liq = estimate_liquidation_price(60000, 5, Side.LONG)
    assert liq < 60000


def test_short_liq_above_entry():
    """空头强平价高于开仓价。"""
    liq = estimate_liquidation_price(60000, 5, Side.SHORT)
    assert liq > 60000


def test_custom_mmr():
    """自定义维持保证金率。"""
    # mmr=1% → 60000 * (1 - 0.2 + 0.01) = 60000 * 0.81 = 48600
    liq = estimate_liquidation_price(60000, 5, Side.LONG, maintenance_margin_rate=0.01)
    assert liq == pytest.approx(48600.0)


def test_invalid_entry_raises():
    """开仓价为 0 或负数时抛异常。"""
    with pytest.raises(ValueError):
        estimate_liquidation_price(0, 5, Side.LONG)
    with pytest.raises(ValueError):
        estimate_liquidation_price(-100, 5, Side.LONG)


def test_invalid_leverage_raises():
    """杠杆为 0 或负数时抛异常。"""
    with pytest.raises(ValueError):
        estimate_liquidation_price(60000, 0, Side.LONG)
    with pytest.raises(ValueError):
        estimate_liquidation_price(60000, -5, Side.LONG)


# ---------------------------------------------------------------------- #
# 强平距离
# ---------------------------------------------------------------------- #
def test_long_distance_positive_when_mark_above_liq():
    """多头：mark 高于 liq 时距离为正。"""
    # mark=58000, liq=48300
    dist = liquidation_distance_pct(58000, 48300, Side.LONG)
    assert dist > 0
    assert dist == pytest.approx(16.72, abs=0.01)


def test_long_distance_decreases_when_price_drops():
    """多头价格下跌时强平距离减少。"""
    liq = 48300
    dist_high = liquidation_distance_pct(58000, liq, Side.LONG)
    dist_low = liquidation_distance_pct(50000, liq, Side.LONG)
    assert dist_low < dist_high


def test_short_distance_positive_when_mark_below_liq():
    """空头：mark 低于 liq 时距离为正。"""
    # mark=62000, liq=71700
    dist = liquidation_distance_pct(62000, 71700, Side.SHORT)
    assert dist > 0


def test_short_distance_decreases_when_price_rises():
    """空头价格上涨时强平距离减少。"""
    liq = 71700
    dist_low = liquidation_distance_pct(62000, liq, Side.SHORT)
    dist_high = liquidation_distance_pct(70000, liq, Side.SHORT)
    assert dist_high < dist_low


def test_long_distance_negative_when_below_liq():
    """多头 mark 低于 liq 时距离为负（已强平）。"""
    dist = liquidation_distance_pct(48000, 48300, Side.LONG)
    assert dist < 0


def test_short_distance_negative_when_above_liq():
    """空头 mark 高于 liq 时距离为负（已强平）。"""
    dist = liquidation_distance_pct(72000, 71700, Side.SHORT)
    assert dist < 0


def test_invalid_mark_price_raises():
    """mark_price 为 0 或负数时抛异常。"""
    with pytest.raises(ValueError):
        liquidation_distance_pct(0, 48300, Side.LONG)


# ---------------------------------------------------------------------- #
# 强平触发判断
# ---------------------------------------------------------------------- #
def test_long_triggers_when_mark_below_liq():
    """多头 mark 低于 liq 时触发强平。"""
    assert should_trigger_liquidation(48000, 48300, Side.LONG) is True


def test_long_not_triggered_when_mark_above_liq():
    """多头 mark 高于 liq 时不触发。"""
    assert should_trigger_liquidation(58000, 48300, Side.LONG) is False


def test_short_triggers_when_mark_above_liq():
    """空头 mark 高于 liq 时触发强平。"""
    assert should_trigger_liquidation(72000, 71700, Side.SHORT) is True


def test_short_not_triggered_when_mark_below_liq():
    """空头 mark 低于 liq 时不触发。"""
    assert should_trigger_liquidation(62000, 71700, Side.SHORT) is False


def test_exact_liquidation_price_triggers():
    """mark 恰好等于 liq 时触发强平。"""
    assert should_trigger_liquidation(48300, 48300, Side.LONG) is True
    assert should_trigger_liquidation(71700, 71700, Side.SHORT) is True


# ---------------------------------------------------------------------- #
# 综合分析
# ---------------------------------------------------------------------- #
def test_analyze_long_safe():
    """多头安全状态分析。"""
    result = analyze_liquidation_risk(60000, 58000, 5, Side.LONG)
    assert result.side == Side.LONG
    assert result.leverage == 5
    assert result.distance_pct > 0
    assert result.is_liquidated is False


def test_analyze_long_liquidated():
    """多头已强平状态分析。"""
    result = analyze_liquidation_risk(60000, 48000, 5, Side.LONG)
    assert result.distance_pct < 0
    assert result.is_liquidated is True


def test_analyze_short_safe():
    """空头安全状态分析。"""
    result = analyze_liquidation_risk(60000, 62000, 5, Side.SHORT)
    assert result.side == Side.SHORT
    assert result.distance_pct > 0
    assert result.is_liquidated is False


def test_analyze_short_liquidated():
    """空头已强平状态分析。"""
    result = analyze_liquidation_risk(60000, 72000, 5, Side.SHORT)
    assert result.distance_pct < 0
    assert result.is_liquidated is True


def test_analyze_includes_all_fields():
    """分析结果包含所有字段。"""
    result = analyze_liquidation_risk(60000, 58000, 5, Side.LONG)
    assert result.entry_price == 60000
    assert result.mark_price == 58000
    assert result.liquidation_price > 0
    assert result.margin_mode == MarginMode.ISOLATED
    assert result.maintenance_margin_rate == 0.005
