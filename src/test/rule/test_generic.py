from __future__ import annotations

from copy import copy
from datetime import datetime, timedelta, timezone
from itertools import chain, product
from typing import TYPE_CHECKING, Callable, List, Type, cast

from pytest import fixture

from ... import Rule
from ...consts import BinaryResolution
from ...market import Market
from ...rule import get_rule
from ...rule.abstract import BinaryRule, VariadicRule
from ...rule.generic import AdditiveRule, ModulusRule, MultiplicitiveRule, NegateRule, ResolveAtTime, ResolveToValue
from ...util import fibonacci

if TYPE_CHECKING:  # pragma: no cover
    from typing import Literal, Optional

    from pytest_regressions.data_regression import DataRegressionFixture

    from ...consts import AnyResolution, PseudoNumericResolution, T
    from .. import PytestRequest

Validator = Callable[[BinaryResolution, BinaryResolution], BinaryResolution]
validators: dict[str, Validator] = {
    "generic.EitherRule": (lambda x, y: bool(x or y)),
    "generic.BothRule": (lambda x, y: bool(x and y)),
    "generic.NeitherRule": (lambda x, y: not (x or y)),
    "generic.NANDRule": (lambda x, y: not (x and y)),
    "generic.XORRule": (lambda x, y: bool(x) != bool(y)),
    "generic.XNORRule": (lambda x, y: bool(x) == bool(y)),
    "generic.ImpliesRule": (lambda x, y: bool((not x) or y)),
    "generic.ConditionalRule": (lambda x, y: "CANCEL" if (not x) else bool(y)),
}


@fixture(params=tuple(validators))  # type: ignore
def binary_rule(request: PytestRequest[str]) -> str:
    return request.param


@fixture(params=(AdditiveRule, MultiplicitiveRule))  # type: ignore
def VariadicRuleSubclass(request: PytestRequest[Type[VariadicRule[T]]]) -> Type[VariadicRule[T]]:
    return request.param


def test_binary_rule(binary_rule: str) -> None:
    RuleSubclass = cast(Type[BinaryRule[BinaryResolution]], get_rule(binary_rule))
    mock_obj1: ResolveToValue[Optional[bool]] = ResolveToValue(None)
    mock_obj2: ResolveToValue[Optional[bool]] = ResolveToValue(None)
    obj = RuleSubclass(cast(Rule[BinaryResolution], mock_obj1), cast(Rule[BinaryResolution], mock_obj2))
    validator = validators[binary_rule]
    mkt: Market = None  # type: ignore[assignment]

    for val1, val2 in list(product(cast(List[bool], [True, False, None]), repeat=2)):
        mock_obj1.resolve_value = val1
        mock_obj2.resolve_value = val2
        expected = bool(validator(val1, val2))
        assert bool(obj.value(mkt, refresh=True)) is expected
        from_dict_val = RuleSubclass.from_dict({
            "rule1": ["generic.ResolveToValue", {"resolve_value": val1}],
            "rule2": ["generic.ResolveToValue", {"resolve_value": val2}]
        })._value(mkt)
        assert from_dict_val == "CANCEL" or bool(from_dict_val) is expected


def test_negate_rule_value() -> None:
    mock_obj: ResolveToValue[Optional[bool]] = ResolveToValue(False)
    obj = NegateRule(cast(Rule[BinaryResolution], mock_obj))

    mkt = cast(Market, None)
    assert bool(obj.value(mkt, refresh=True)) is True
    assert NegateRule.from_dict({
        "child": ["generic.ResolveToValue", {"resolve_value": False}]
    })._value(mkt) is True

    mock_obj.resolve_value = True
    assert bool(obj.value(mkt, refresh=True)) is False
    assert NegateRule.from_dict({
        "child": ["generic.ResolveToValue", {"resolve_value": True}]
    })._value(mkt) is False


def test_at_time_rule_value() -> None:
    now = datetime.now()
    utcnow = datetime.now(timezone.utc)
    offsets = [
        timedelta(minutes=5)
    ]
    values = chain.from_iterable(
        (now + offset, now - offset, utcnow + offset, utcnow - offset)
        for offset in offsets
    )
    for idx, val in enumerate(values):
        obj = ResolveAtTime(val)
        assert bool(obj.value(cast(Market, None))) is bool(idx % 2)


def test_modulus_rule(data_regression: DataRegressionFixture, limit: int = 100) -> None:
    val1: ResolveToValue[Literal['CANCEL'] | float] = ResolveToValue(1)
    val2: ResolveToValue[Literal['CANCEL'] | float] = ResolveToValue(1)
    rule = ModulusRule(val1, val2)
    data: dict[tuple[int, float], AnyResolution] = {}
    mkt: Market = None  # type: ignore[assignment]
    prev = 1
    prev_desc: str = ''
    for idx, x in enumerate(fibonacci(start=2)):
        if idx >= limit:
            break
        val1.resolve_value = x
        val2.resolve_value = prev
        desc = rule.explain_abstract()
        assert desc != prev_desc
        assert len(desc) >= len(prev_desc)
        prev_desc = desc
        val = rule.value(mkt, refresh=True)
        data[(x, prev)] = val
        prev = x
    data_regression.check({'answer': data})


def test_variadic_rule(
    VariadicRuleSubclass: Type[VariadicRule[PseudoNumericResolution]],
    data_regression: DataRegressionFixture,
    limit: int = 100
) -> None:
    rule = VariadicRuleSubclass()
    if VariadicRuleSubclass == MultiplicitiveRule:
        limit //= 10
    data: dict[int, AnyResolution] = {}
    mkt: Market = None  # type: ignore[assignment]
    prev_desc: str = ''
    for idx, x in enumerate(fibonacci(start=2)):
        if idx >= limit:
            break
        rule.rules.append(ResolveToValue(copy(x)))
        desc = rule.explain_abstract()
        assert desc != prev_desc
        assert len(desc) >= len(prev_desc)
        prev_desc = desc
        data[x] = rule.value(mkt, refresh=True)
    data_regression.check({'answer': data})
