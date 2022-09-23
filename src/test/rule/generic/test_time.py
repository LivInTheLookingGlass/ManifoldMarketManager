from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import chain, product
from typing import TYPE_CHECKING, Any, Optional, cast

from ....rule.generic.time import BothRule, EitherRule, NegateRule, ResolveAtTime

if TYPE_CHECKING:
    from ....market import Market


@dataclass
class MockRule:
    val: Optional[bool] = None

    def value(self, market: Any) -> Optional[bool]:
        return self.val


def test_negate_rule_value() -> None:
    mock_obj = MockRule()
    obj = NegateRule(mock_obj)

    mock_obj.val = True
    assert obj.value(cast('Market', None)) is False

    mock_obj.val = False
    assert obj.value(cast('Market', None)) is True


def test_either_rule_value() -> None:
    mock_obj1 = MockRule()
    mock_obj2 = MockRule()
    obj = EitherRule(mock_obj1, mock_obj2)

    for val1, val2 in product([True, False, None], repeat=2):
        mock_obj1.val = val1
        mock_obj2.val = val2
        assert obj.value(cast('Market', None)) is (val1 or val2)


def test_both_rule_value() -> None:
    mock_obj1 = MockRule()
    mock_obj2 = MockRule()
    obj = BothRule(mock_obj1, mock_obj2)

    for val1, val2 in product([True, False, None], repeat=2):
        mock_obj1.val = val1
        mock_obj2.val = val2
        assert obj.value(cast('Market', None)) is (val1 and val2)


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
        assert obj.value(cast('Market', None)) is bool(idx % 2)
