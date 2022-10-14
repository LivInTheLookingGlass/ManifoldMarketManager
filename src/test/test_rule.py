from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from pytest import fixture, raises, skip

from .. import Rule
from ..consts import AVAILABLE_RULES, Outcome
from ..rule import get_rule
from ..rule.generic import ResolveToValue

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ..market import Market
    from . import PytestRequest


@fixture(params=AVAILABLE_RULES)  # type: ignore
def rule_name(request: PytestRequest[str]) -> str:
    """Return the name of an existing rule."""
    return request.param


def test_import_rule(rule_name: str) -> None:
    """Make sure this function can import any existing rule."""
    assert issubclass(get_rule(rule_name), Rule)


def test_import_rule_failure() -> None:
    """Make sure this function can't import arbitrary objects."""
    for rule_name in ["time.sleep", "random.Random"]:
        with raises(Exception):
            get_rule(rule_name)


def test_rule_formatting() -> None:
    """Make sure that Rule does formatting if requested."""
    market: Market = None  # type: ignore[assignment]
    for outcome, as_int in [(100, 100), ({3: 1}, 3), ([7], 7), ("25", 25), (None, None)]:
        rule = ResolveToValue(outcome)  # type: ignore
        val: Any = rule.value(market, format=Outcome.BINARY, refresh=True)
        assert isinstance(val, (int, float)) or as_int is None
        assert val == as_int

        val = rule.value(market, format=Outcome.PSEUDO_NUMERIC)
        assert isinstance(val, (int, float)) or as_int is None
        assert val == as_int

        val = rule.value(market, format=Outcome.FREE_RESPONSE)
        if as_int is not None:
            assert isinstance(val, Mapping)
            assert as_int in val
            assert val[as_int] == 1

        val = rule.value(market, format=Outcome.MULTIPLE_CHOICE)
        if as_int is not None:
            assert isinstance(val, Mapping)
            assert as_int in val
            assert val[as_int] == 1

    rule = ResolveToValue(object())  # type: ignore
    for format in Outcome:
        with raises(TypeError):
            val = rule.value(market, format=format, refresh=True)


def test_rule_from_dict(rule_name: str) -> None:
    """Make sure that if `__init__` doesn't require arguments, `from_dict()` also does not."""
    RuleSubclass = get_rule(rule_name)
    try:
        RuleSubclass()
    except Exception:
        skip("Cannot instantiate with default arguments, may be tested elsewhere")
    RuleSubclass.from_dict({})
