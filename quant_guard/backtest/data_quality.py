"""quant_guard.backtest.data_quality: 历史数据完整性校验。

对历史 K 线进行缺失、重复、OHLC 逻辑异常、volume 异常检查，
输出 DataQualityReport，用于回测前的数据质量门禁。
"""

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

# 时间框架 → 秒数（用于检测时间戳缺口）
_TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
}


@dataclass
class DataQualityIssue:
    """单项数据质量问题。

    severity:
        - "error": 严重问题（重复/逻辑违反/负价格），回测前必须修复
        - "warning": 可疑问题（缺失/零成交量/极端成交量），需人工确认
    """

    check: str
    severity: str
    count: int
    sample: list = field(default_factory=list)

    def __post_init__(self) -> None:
        # 样本最多保留 5 条，避免报告过长
        self.sample = list(self.sample)[:5]


@dataclass
class DataQualityReport:
    """数据质量报告。"""

    symbol: str
    timeframe: str
    rows: int
    issues: List[DataQualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """无 error 级问题即视为通过。"""
        return not any(i.severity == "error" for i in self.issues)

    def summary(self) -> str:
        """返回可读的报告摘要。"""
        lines = [
            f"DataQualityReport: {self.symbol} {self.timeframe} "
            f"({self.rows} rows)"
        ]
        if not self.issues:
            lines.append("  no issues found")
        for i in self.issues:
            lines.append(
                f"  [{i.severity.upper()}] {i.check}: {i.count} "
                f"(sample: {i.sample})"
            )
        lines.append(f"  => {'PASSED' if self.passed else 'FAILED'}")
        return "\n".join(lines)


# ---------------------------------------------------------------------- #
# 单项检查
# ---------------------------------------------------------------------- #
def check_missing_timestamps(
    df: pd.DataFrame, timeframe: str
) -> List[DataQualityIssue]:
    """检测时间戳缺口（相邻差值大于预期间隔）。"""
    expected_ms = _TIMEFRAME_SECONDS.get(timeframe, 0) * 1000
    if expected_ms == 0 or len(df) < 2:
        return []
    ts = df["timestamp"].sort_values().values
    diffs = np.diff(ts)
    gap_idx = np.where(diffs > expected_ms)[0]
    if len(gap_idx) == 0:
        return []
    samples = [
        {"after": int(ts[i]), "gap_ms": int(diffs[i])} for i in gap_idx
    ]
    return [
        DataQualityIssue(
            check="missing_timestamps",
            severity="warning",
            count=len(gap_idx),
            sample=samples,
        )
    ]


def check_duplicate_timestamps(df: pd.DataFrame) -> List[DataQualityIssue]:
    """检测重复时间戳。"""
    dup_mask = df["timestamp"].duplicated(keep=False)
    dup_count = int(dup_mask.sum())
    if dup_count == 0:
        return []
    samples = sorted(df.loc[dup_mask, "timestamp"].unique().tolist())
    return [
        DataQualityIssue(
            check="duplicate_timestamps",
            severity="error",
            count=dup_count,
            sample=samples,
        )
    ]


def check_ohlc_logic(df: pd.DataFrame) -> List[DataQualityIssue]:
    """检测 OHLC 逻辑异常：high<low、high<max(open,close)、
    low>min(open,close)、负价格。"""
    issues: List[DataQualityIssue] = []

    bad = df[df["high"] < df["low"]]
    if not bad.empty:
        issues.append(
            DataQualityIssue(
                "high_lt_low", "error", len(bad), bad["timestamp"].tolist()
            )
        )

    oc_max = df[["open", "close"]].max(axis=1)
    bad = df[df["high"] < oc_max]
    if not bad.empty:
        issues.append(
            DataQualityIssue(
                "high_lt_oc_max", "error", len(bad), bad["timestamp"].tolist()
            )
        )

    oc_min = df[["open", "close"]].min(axis=1)
    bad = df[df["low"] > oc_min]
    if not bad.empty:
        issues.append(
            DataQualityIssue(
                "low_gt_oc_min", "error", len(bad), bad["timestamp"].tolist()
            )
        )

    neg = df[(df["open"] < 0) | (df["high"] < 0) | (df["low"] < 0) | (df["close"] < 0)]
    if not neg.empty:
        issues.append(
            DataQualityIssue(
                "negative_price", "error", len(neg), neg["timestamp"].tolist()
            )
        )

    return issues


def check_volume_anomaly(df: pd.DataFrame) -> List[DataQualityIssue]:
    """检测 volume 异常：非正、极端离群值（|z|>10）。"""
    issues: List[DataQualityIssue] = []

    nonpos = df[df["volume"] <= 0]
    if not nonpos.empty:
        issues.append(
            DataQualityIssue(
                "non_positive_volume",
                "warning",
                len(nonpos),
                nonpos["timestamp"].tolist(),
            )
        )

    vol = df["volume"]
    median = float(vol.median())
    # 极端成交量：超过中位数 50 倍（中位数为正时）。
    # 用中位数倍数而非 z-score，避免单个极端值拉高均值/标准差导致漏检。
    if median > 0:
        extreme = df[vol > median * 50]
        if not extreme.empty:
            issues.append(
                DataQualityIssue(
                    "extreme_volume",
                    "warning",
                    len(extreme),
                    extreme["timestamp"].tolist(),
                )
            )

    return issues


# ---------------------------------------------------------------------- #
# 主入口
# ---------------------------------------------------------------------- #
def validate(
    df: pd.DataFrame, symbol: str = "", timeframe: str = "15m"
) -> DataQualityReport:
    """对 K 线 DataFrame 执行全部数据质量检查。

    要求 df 包含列: timestamp(ms), open, high, low, close, volume。
    """
    issues: List[DataQualityIssue] = []
    issues.extend(check_missing_timestamps(df, timeframe))
    issues.extend(check_duplicate_timestamps(df))
    issues.extend(check_ohlc_logic(df))
    issues.extend(check_volume_anomaly(df))
    return DataQualityReport(
        symbol=symbol, timeframe=timeframe, rows=len(df), issues=issues
    )
