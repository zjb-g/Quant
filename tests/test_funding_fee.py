"""tests/test_funding_fee: 资金费计算模块测试。"""

import pytest

from quant_guard.backtest.funding_fee import (
    accumulate_funding_fees,
    calculate_funding_fee,
    calculate_funding_fee_series,
)
from quant_guard.exchange.models import Side


# ---------------------------------------------------------------------- #
# 单次计算：方向正确性
# ---------------------------------------------------------------------- #
def test_long_positive_rate_pays_fee():
    """多头 + 正费率 = 多头付费（正数）。"""
    entry = calculate_funding_fee(1000, 0.0001, Side.LONG)
    assert entry.fee == pytest.approx(0.1)
    assert entry.fee > 0  # 成本支出


def test_short_positive_rate_receives_fee():
    """空头 + 正费率 = 空头收费（负数）。"""
    entry = calculate_funding_fee(1000, 0.0001, Side.SHORT)
    assert entry.fee == pytest.approx(-0.1)
    assert entry.fee < 0  # 收益收入


def test_long_negative_rate_receives_fee():
    """多头 + 负费率 = 多头收费（负数）。"""
    entry = calculate_funding_fee(1000, -0.0001, Side.LONG)
    assert entry.fee == pytest.approx(-0.1)
    assert entry.fee < 0


def test_short_negative_rate_pays_fee():
    """空头 + 负费率 = 空头付费（正数）。"""
    entry = calculate_funding_fee(1000, -0.0001, Side.SHORT)
    assert entry.fee == pytest.approx(0.1)
    assert entry.fee > 0


def test_zero_rate_zero_fee():
    """费率为 0 时费用为 0。"""
    entry = calculate_funding_fee(1000, 0.0, Side.LONG)
    assert entry.fee == 0.0


def test_zero_notional_zero_fee():
    """名义价值为 0 时费用为 0。"""
    entry = calculate_funding_fee(0, 0.0001, Side.LONG)
    assert entry.fee == 0.0


def test_negative_notional_raises():
    """名义价值为负数时抛异常。"""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_funding_fee(-100, 0.0001, Side.LONG)


# ---------------------------------------------------------------------- #
# 边界值
# ---------------------------------------------------------------------- #
def test_large_notional():
    """大额持仓计算正确。"""
    entry = calculate_funding_fee(1000000, 0.0001, Side.LONG)
    assert entry.fee == pytest.approx(100.0)


def test_tiny_rate():
    """极小费率计算正确。"""
    entry = calculate_funding_fee(1000, 0.000001, Side.LONG)
    assert entry.fee == pytest.approx(0.001)


def test_large_rate():
    """极端费率（0.1%=0.001）计算正确。"""
    entry = calculate_funding_fee(1000, 0.001, Side.LONG)
    assert entry.fee == pytest.approx(1.0)


# ---------------------------------------------------------------------- #
# 多周期累加
# ---------------------------------------------------------------------- #
def test_accumulate_multiple_periods():
    """多周期累加正确。"""
    entries = [
        calculate_funding_fee(1000, 0.0001, Side.LONG, 1000),
        calculate_funding_fee(1000, 0.0002, Side.LONG, 2000),
        calculate_funding_fee(1000, -0.0001, Side.LONG, 3000),
    ]
    summary = accumulate_funding_fees(entries)
    assert summary.count == 3
    # 0.1 + 0.2 - 0.1 = 0.2
    assert summary.total_fee == pytest.approx(0.2)


def test_series_long_accumulate():
    """多头连续 3 个 8h 周期累加。"""
    rates = [0.0001, 0.0001, 0.0001]
    summary = calculate_funding_fee_series(1000, rates, Side.LONG)
    assert summary.count == 3
    assert summary.total_fee == pytest.approx(0.3)


def test_series_short_accumulate():
    """空头连续 3 个 8h 周期累加（收费）。"""
    rates = [0.0001, 0.0001, 0.0001]
    summary = calculate_funding_fee_series(1000, rates, Side.SHORT)
    assert summary.count == 3
    assert summary.total_fee == pytest.approx(-0.3)


def test_series_mixed_rates():
    """混合正负费率累加。"""
    rates = [0.0001, -0.0002, 0.0001, -0.0001]
    summary = calculate_funding_fee_series(1000, rates, Side.LONG)
    assert summary.count == 4
    # 0.1 - 0.2 + 0.1 - 0.1 = -0.1
    assert summary.total_fee == pytest.approx(-0.1)


def test_series_timestamps():
    """时间戳正确传递。"""
    rates = [0.0001, 0.0001]
    timestamps = [1000, 2000]
    summary = calculate_funding_fee_series(1000, rates, Side.LONG, timestamps)
    assert summary.entries[0].timestamp == 1000
    assert summary.entries[1].timestamp == 2000


def test_series_length_mismatch_raises():
    """timestamps 与 rates 长度不匹配时抛异常。"""
    with pytest.raises(ValueError, match="length"):
        calculate_funding_fee_series(1000, [0.0001, 0.0001], Side.LONG, [1000])


def test_empty_series():
    """空费率列表返回空汇总。"""
    summary = calculate_funding_fee_series(1000, [], Side.LONG)
    assert summary.count == 0
    assert summary.total_fee == 0.0


# ---------------------------------------------------------------------- #
# 实际场景：8h 结算频率
# ---------------------------------------------------------------------- #
def test_daily_funding_cost_3_settlements():
    """一天 3 次 8h 结算的总成本。"""
    # 假设持仓 500 USDT，每次费率 0.01%
    daily_cost = calculate_funding_fee_series(
        500, [0.0001, 0.0001, 0.0001], Side.LONG
    )
    assert daily_cost.total_fee == pytest.approx(0.15)
    assert daily_cost.count == 3


def test_weekly_funding_cost():
    """一周 21 次 8h 结算的总成本。"""
    rates = [0.0001] * 21  # 7 天 * 3 次/天
    weekly = calculate_funding_fee_series(1000, rates, Side.LONG)
    assert weekly.count == 21
    assert weekly.total_fee == pytest.approx(2.1)
