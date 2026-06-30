"""quant_guard.ai.deepseek: DeepSeek AI 策略生成器。

用户用自然语言描述策略，AI 生成 Freqtrade 兼容的策略 Python 代码。
"""

import json
import os
from typing import Optional

import httpx


SYSTEM_PROMPT = """你是一个 Freqtrade 量化策略专家。用户会用自然语言描述交易策略，你需要将其转换为 Freqtrade IStrategy 兼容的 Python 代码。

要求：
1. 必须继承 IStrategy，类名用 PascalCase
2. INTERFACE_VERSION = 3
3. timeframe 用 "15m"（除非用户特别指定）
4. can_short = True（支持双向持仓）
5. max_leverage = 5.0
6. 实现 populate_indicators / populate_entry_trend / populate_exit_trend
7. 使用 talib.abstract 计算指标
8. 信号用 dataframe.loc[condition, "enter_long"] = 1 等标准格式
9. 参数用 DecimalParameter（签名：DecimalParameter(low, high, default=X, space="buy")）
10. 加杠杆方法：def leverage(self, ...): return min(5.0, max_leverage)
11. minimal_roi 和 stoploss 必须设置
12. 代码必须完整可运行，不要省略
13. 中文注释说明每个信号含义
14. 只输出 Python 代码，不要输出其他文字

输出格式：
```python
# 策略说明
# ...注释...

import ...

class XxxStrategy(IStrategy):
    ...
```"""


class DeepSeekClient:
    """DeepSeek API 客户端。

    API Key 从环境变量 DEEPSEEK_API_KEY 读取。
    用户可在 https://platform.deepseek.com 获取。
    """

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_strategy(self, description: str) -> str:
        """用自然语言描述生成 Freqtrade 策略代码。

        参数：
            description: 策略的自然语言描述

        返回：
            生成的 Python 策略代码字符串

        异常：
            RuntimeError: API 未配置或调用失败
        """
        if not self.is_configured:
            raise RuntimeError(
                "DeepSeek API 未配置。请设置环境变量 DEEPSEEK_API_KEY。"
                "在 https://platform.deepseek.com 获取 API Key。"
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": description},
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
        }

        try:
            with httpx.Client(timeout=180) as client:
                resp = client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return self._extract_code(content)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"DeepSeek API 错误: {e.response.status_code} {e.response.text[:200]}") from e
        except Exception as e:
            raise RuntimeError(f"DeepSeek API 调用失败: {e}") from e

    def _extract_code(self, content: str) -> str:
        """从 AI 回复中提取 Python 代码（兼容缺少闭合 ``` 或被截断的回复）。"""
        text = content.strip()
        code = ""

        if "```python" in text:
            start = text.index("```python") + len("```python")
            rest = text[start:]
            end = rest.find("```")
            code = rest[:end].strip() if end != -1 else rest.strip()
        elif "```" in text:
            start = text.index("```") + 3
            rest = text[start:].lstrip()
            if rest.lower().startswith("python"):
                rest = rest[6:].lstrip("\n\r")
            end = rest.find("```")
            code = rest[:end].strip() if end != -1 else rest.strip()
        else:
            code = text

        if not code or "class " not in code or "IStrategy" not in code:
            raise RuntimeError(
                "AI 未返回完整策略代码（可能被截断）。请简化策略描述，或减少指标数量后重试。"
            )
        return code

    def refine_strategy(self, code: str, feedback: str) -> str:
        """根据用户反馈修改已有策略代码。

        参数：
            code: 现有策略代码
            feedback: 修改意见

        返回：
            修改后的策略代码
        """
        prompt = f"""以下是现有的 Freqtrade 策略代码，请根据用户意见修改：

```python
{code}
```

用户修改意见：{feedback}

请输出修改后的完整策略代码。"""
        return self.generate_strategy(prompt)

    TRADE_ANALYSIS_PROMPT = """你是专业的加密货币 USDT 永续合约交易分析师。
用户会提供实盘历史持仓的统计数据与样本交易，请深入分析交易模式、漏洞与改进方向。

要求：
1. 用中文回答，结构清晰（概览 → 模式发现 → 风险漏洞 → 改进建议 → 执行清单）
2. 结合胜率、杠杆分布、持仓时长、多空差异、手续费/资金费给出具体结论
3. 指出可能的情绪化交易、过度交易、杠杆滥用、止损缺失等问题
4. 改进建议要可执行（参数、规则、风控阈值），不要空泛
5. 若数据样本不足，明确说明局限性
6. 不要编造数据中不存在的数字"""

    def analyze_trades(self, stats: dict, sample_trades: list[dict]) -> str:
        """基于历史持仓统计生成 AI 交易复盘分析。"""
        if not self.is_configured:
            raise RuntimeError(
                "DeepSeek API 未配置。请设置环境变量 DEEPSEEK_API_KEY。"
            )

        payload_text = json.dumps(
            {"statistics": stats, "sample_trades": sample_trades[:40]},
            ensure_ascii=False,
            indent=2,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.TRADE_ANALYSIS_PROMPT},
                {
                    "role": "user",
                    "content": f"请分析以下实盘历史持仓数据：\n\n{payload_text}",
                },
            ],
            "temperature": 0.4,
            "max_tokens": 4096,
        }

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"DeepSeek API 错误: {e.response.status_code} {e.response.text[:200]}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"DeepSeek API 调用失败: {e}") from e
