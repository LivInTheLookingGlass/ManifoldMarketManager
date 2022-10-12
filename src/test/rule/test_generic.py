from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import chain, product
from typing import TYPE_CHECKING, Callable, List, Type, cast

from pytest import fixture

from ... import Rule
from ...consts import BinaryResolution
from ...market import Market
from ...rule import get_rule
from ...rule.abstract import BinaryRule
from ...rule.generic import NegateRule, ResolveAtTime, ResolveToValue

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional

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
}


@fixture(params=tuple(validators))  # type: ignore
def binary_rule(request: PytestRequest[str]) -> str:
    return request.param


def test_binary_rule(binary_rule: str) -> None:
    RuleSubclass = cast(Type[BinaryRule[BinaryResolution]], get_rule(binary_rule))
    mock_obj1: ResolveToValue[Optional[bool]] = ResolveToValue(None)
    mock_obj2: ResolveToValue[Optional[bool]] = ResolveToValue(None)
    obj = RuleSubclass(cast(Rule[BinaryResolution], mock_obj1), cast(Rule[BinaryResolution], mock_obj2))
    validator = validators[binary_rule]

    for val1, val2 in list(product(cast(List[bool], [True, False, None]), repeat=2)):
        mock_obj1.resolve_value = val1
        mock_obj2.resolve_value = val2
        assert bool(obj._value(cast(Market, None))) is bool(validator(val1, val2))


def test_negate_rule_value() -> None:
    mock_obj: ResolveToValue[Optional[bool]] = ResolveToValue(False)
    obj = NegateRule(cast(Rule[BinaryResolution], mock_obj))

    mkt = cast(Market, None)
    assert bool(obj._value(mkt)) is True

    mock_obj.resolve_value = True
    assert bool(obj._value(mkt)) is False


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
        assert bool(obj._value(cast(Market, None))) is bool(idx % 2)
