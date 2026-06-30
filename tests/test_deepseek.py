from quant_guard.ai.deepseek import DeepSeekClient


def test_extract_code_without_closing_fence():
    client = DeepSeekClient(api_key="test")
    content = "```python\nclass FooStrategy(IStrategy):\n    pass\n"
    code = client._extract_code(content)
    assert "class FooStrategy" in code


def test_extract_code_plain():
    client = DeepSeekClient(api_key="test")
    content = "class BarStrategy(IStrategy):\n    INTERFACE_VERSION = 3\n"
    code = client._extract_code(content)
    assert "BarStrategy" in code


def test_extract_code_invalid_raises():
    client = DeepSeekClient(api_key="test")
    try:
        client._extract_code("这是一段没有代码的文字")
        assert False, "should raise"
    except RuntimeError as e:
        assert "未返回完整策略代码" in str(e)
