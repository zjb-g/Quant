"""tests/test_data_quality: 数据完整性校验模块测试。"""

import pandas as pd

from quant_guard.backtest.data_quality import (
    DataQualityReport,
    validate,
)

BASE_TS = 1700000000000
STEP_15M = 900_000  # 15 分钟对应的毫秒数


def _make_df(rows):
    """rows: list of (ts, o, h, l, c, v)。"""
    return pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )


def _clean_rows(n=20):
    return [
        (BASE_TS + i * STEP_15M, 100.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(n)
    ]


# ---------------------------------------------------------------------- #
# 正常数据
# ---------------------------------------------------------------------- #
def test_clean_data_passes():
    rep = validate(_make_df(_clean_rows(20)), "BTC/USDT:USDT", "15m")
    assert isinstance(rep, DataQualityReport)
    assert rep.rows == 20
    assert rep.passed is True
    assert rep.issues == []


def test_summary_passed():
    rep = validate(_make_df(_clean_rows(5)), "BTC/USDT:USDT", "15m")
    assert "PASSED" in rep.summary()


# ---------------------------------------------------------------------- #
# 缺失时间戳
# ---------------------------------------------------------------------- #
def test_missing_timestamps_detected():
    rows = _clean_rows(20)
    rows.pop(10)  # 删除中间一根
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    missing = [i for i in rep.issues if i.check == "missing_timestamps"]
    assert len(missing) == 1
    assert missing[0].count >= 1
    # 缺失是 warning，不影响 passed
    assert rep.passed is True


def test_no_missing_when_continuous():
    rep = validate(_make_df(_clean_rows(10)), "ETH/USDT:USDT", "15m")
    assert not any(i.check == "missing_timestamps" for i in rep.issues)


# ---------------------------------------------------------------------- #
# 重复时间戳
# ---------------------------------------------------------------------- #
def test_duplicate_timestamps_detected():
    rows = _clean_rows(10)
    rows.append(rows[5])  # 重复第 5 根
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    dup = [i for i in rep.issues if i.check == "duplicate_timestamps"]
    assert len(dup) == 1
    assert dup[0].severity == "error"
    assert rep.passed is False


# ---------------------------------------------------------------------- #
# OHLC 逻辑异常
# ---------------------------------------------------------------------- #
def test_high_lt_low_detected():
    rows = [
        (BASE_TS + i * STEP_15M, 100.0, 95.0, 105.0, 100.0, 10.0)
        for i in range(5)
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    assert any(i.check == "high_lt_low" for i in rep.issues)
    assert rep.passed is False


def test_high_lt_oc_max_detected():
    rows = [
        (BASE_TS + i * STEP_15M, 100.0, 100.5, 99.0, 101.0, 10.0)
        for i in range(5)  # close=101 > high=100.5
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    assert any(i.check == "high_lt_oc_max" for i in rep.issues)


def test_low_gt_oc_min_detected():
    rows = [
        (BASE_TS + i * STEP_15M, 100.0, 101.0, 100.5, 99.0, 10.0)
        for i in range(5)  # low=100.5 > close=99
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    assert any(i.check == "low_gt_oc_min" for i in rep.issues)


def test_negative_price_detected():
    rows = [
        (BASE_TS + i * STEP_15M, -1.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(5)
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    assert any(i.check == "negative_price" for i in rep.issues)


# ---------------------------------------------------------------------- #
# volume 异常
# ---------------------------------------------------------------------- #
def test_non_positive_volume_detected():
    rows = [
        (BASE_TS + i * STEP_15M, 100.0, 101.0, 99.0, 100.0, 0.0)
        for i in range(5)
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    vol = [i for i in rep.issues if i.check == "non_positive_volume"]
    assert len(vol) == 1
    assert vol[0].severity == "warning"


def test_extreme_volume_detected():
    rows = _clean_rows(20)
    rows[-1] = (rows[-1][0], 100.0, 101.0, 99.0, 100.0, 100000.0)  # 极端成交量
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    assert any(i.check == "extreme_volume" for i in rep.issues)


def test_sample_truncated_to_five():
    """issue.sample 最多保留 5 条。"""
    rows = [
        (BASE_TS + i * STEP_15M, -1.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(10)  # 10 根全部负价格
    ]
    rep = validate(_make_df(rows), "BTC/USDT:USDT", "15m")
    neg = [i for i in rep.issues if i.check == "negative_price"][0]
    assert len(neg.sample) <= 5
