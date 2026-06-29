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
                content = data["choices"][0]["message"]["content"]
                return self._extract_code(content)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"DeepSeek API 错误: {e.response.status_code} {e.response.text[:200]}") from e
        except Exception as e:
            raise RuntimeError(f"DeepSeek API 调用失败: {e}") from e

    def _extract_code(self, content: str) -> str:
        """从 AI 回复中提取 Python 代码。"""
        # 尝试提取 ```python ... ``` 代码块
        if "```python" in content:
            start = content.index("```python") + len("```python")
            end = content.index("```", start)
            return content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            return content[start:end].strip()
        # 没有代码块，返回原文
        return content.strip()

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
