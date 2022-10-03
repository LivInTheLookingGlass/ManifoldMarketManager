from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import chain, product
from typing import TYPE_CHECKING, cast

from ...market import Market
from ...rule.generic import BothRule, EitherRule, NegateRule, ResolveAtTime, ResolveToValue

if TYPE_CHECKING:
    ...


def test_negate_rule_value() -> None:
    mock_obj = ResolveToValue(False)
    obj = NegateRule(mock_obj)

    mkt = cast(Market, None)
    assert bool(obj._value(mkt)) is True

    mock_obj.resolve_value = True
    assert bool(obj._value(mkt)) is False


def test_either_rule_value() -> None:
    mock_obj1 = ResolveToValue(None)
    mock_obj2 = ResolveToValue(None)
    obj = EitherRule(mock_obj1, mock_obj2)

    for val1, val2 in product(cast(list[bool], [True, False, None]), repeat=2):
        mock_obj1.resolve_value = val1
        mock_obj2.resolve_value = val2
        assert bool(obj._value(cast(Market, None))) is bool(val1 or val2)


def test_both_rule_value() -> None:
    mock_obj1 = ResolveToValue(None)
    mock_obj2 = ResolveToValue(None)
    obj = BothRule(mock_obj1, mock_obj2)

    for val1, val2 in product(cast(list[bool], [True, False, None]), repeat=2):
        mock_obj1.resolve_value = val1
        mock_obj2.resolve_value = val2
        assert bool(obj._value(cast(Market, None))) is bool(val1 and val2)


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
