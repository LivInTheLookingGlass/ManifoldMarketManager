from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from os import environ
from random import randrange
from secrets import token_hex
from typing import TYPE_CHECKING, Any, List, cast

from pytest import raises

from .. import Rule
from ..consts import Outcome
from ..util import explain_abstract, fibonacci, market_to_answer_map, require_env
from . import mkt

if TYPE_CHECKING:  # pragma: no cover
    from ..market import Market

assert mkt  # just need to access so mypy doesn't complain

canonical_market_answers: dict[str, dict[int, float]] = {
    'cUDUvkVTXKuuyIkf0Fpz': {0: 0.22615331252167883, 1: 0.36351023239680885, 2: 0.4103364550815123},
    'Dx7vPilTr1rgQQVETM2Z': {
        0: 0.09812875918912897, 1: 0.15666072621964802, 2: 0.11795500111383382, 3: 0.06961461349966586,
        4: 0.18021831142793496, 5: 0.09300512363555358, 6: 0.2148028514145689, 7: 0.06961461349966586
    },
    'opaEWymtuX61FK2gKwXL': {
        1: 0.26100396143128424, 2: 0.006859570407866334, 3: 0.01669465122085362, 4: 0.054204550575922335,
        5: 0.09407410845073831, 6: 0.016964979118700572, 7: 0.007332644229098495, 8: 0.07603923891347701,
        9: 0.0074678081780219716, 10: 0.007535390152483708, 11: 0.01723530701654752, 12: 0.04240768897474015,
        13: 0.044097238336283574, 14: 0.010172990685295974
    },
    'GdIMBXtOnA1wj3KJAYvj': {
        1: 0.011620129465247311, 2: 0.01218696504891791, 3: 0.012753800632588509, 4: 0.03503043907084311,
        5: 0.10169030371050575, 6: 0.09063700982892904, 7: 0.018988992052965115, 8: 0.05807797390288972,
        9: 0.03832942216780601, 10: 0.09205409878810553, 11: 0.02545091770680996, 12: 0.005271570928136584,
        13: 0.011132650863290594, 14: 0.005316917774830232, 15: 0.0, 16: 0.05441621603237766, 17: 0.005566325431645297,
        18: 0.005588998854992122, 19: 0.05713702683399654, 20: 0.1278440975410672, 21: 0.025484927841830193,
        22: 0.06529945923885318, 23: 0.00665464975229285, 24: 0.006677323175639674, 25: 0.006699996598986498,
        26: 0.006722670022333324
    },
}


def test_market_to_answer_map(mkt: Market) -> None:
    """Test the behavior of the market to answer map utility function."""
    if mkt.market.outcomeType in Outcome.MC_LIKE():
        answer = market_to_answer_map(mkt)
        print(mkt.id, answer)
        assert answer == canonical_market_answers[mkt.id]
    else:
        with raises(RuntimeError):
            market_to_answer_map(mkt)


def test_fib(limit: int = 100) -> None:
    """Ensure the fib generator works, out to some number of terms."""
    penultimate = prev = 0
    for idx, x in enumerate(fibonacci(start=randrange(0, 20))):
        if idx >= 2:
            assert x - prev == penultimate
        penultimate = prev
        prev = x
        if idx >= limit:
            break


def test_require_env() -> None:
    """Make sure that we are actually requiring environment variables when specified."""
    for _ in range(10):
        key = token_hex(16)

        @require_env(key)
        def test_func() -> None:
            ...

        orig = environ.get(key)
        try:
            if orig is not None:
                del environ[key]
            with raises(EnvironmentError):
                test_func()
            environ[key] = 'example'
            test_func()
        finally:
            if orig is None:
                del environ[key]
            else:
                environ[key] = orig


def test_explain_abstract() -> None:
    """Make sure that explain_abstract() calls to each of its fed Rules."""
    @dataclass
    class MockObject:
        called: bool = False

        def explain_abstract(self, **kwargs: Any) -> str:
            self.called = True
            return ""

    l1 = [MockObject() for _ in range(randrange(20))]
    l2 = [MockObject() for _ in range(randrange(20))]
    val = explain_abstract(cast(List[Rule[Any]], l1), cast(List[Rule[Any]], l2))
    assert isinstance(val, str)
    for obj in chain(l1, l2):
        assert obj.called
