from quant_guard.services.strategy_manager import resolve_strategy_name


def test_resolve_strategy_name_by_stem():
    assert resolve_strategy_name("move") == "ConsecutiveBodyExpansionStrategy"


def test_resolve_strategy_name_by_class():
    assert resolve_strategy_name("EmaCrossoverStrategy") == "EmaCrossoverStrategy"


def test_resolve_strategy_name_by_filename():
    assert resolve_strategy_name("move.py") == "ConsecutiveBodyExpansionStrategy"
