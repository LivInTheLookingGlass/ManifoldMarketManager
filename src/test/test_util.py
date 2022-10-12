from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from os import environ
from random import randrange
from secrets import token_hex
from typing import TYPE_CHECKING, Any, List, Mapping, cast

from pytest import raises, skip

from .. import Rule
from ..consts import Outcome
from ..util import (explain_abstract, fibonacci, market_to_answer_map, pool_to_number_cpmm1, pool_to_prob_cpmm1,
                    prob_to_number_cpmm1, require_env)
from . import mkt

if TYPE_CHECKING:  # pragma: no cover
    from pytest_benchmark.fixture import BenchmarkFixture
    from pytest_regressions.data_regression import DataRegressionFixture

    from ..market import Market

assert mkt  # just need to access so mypy doesn't complain


def test_market_to_answer_map(mkt: Market, data_regression: DataRegressionFixture, benchmark: BenchmarkFixture) -> None:
    """Test the behavior of the market to answer map utility function."""
    if mkt.market.outcomeType in Outcome.MC_LIKE():
        answer = benchmark(market_to_answer_map, mkt)
        data_regression.check(answer)
    else:
        with raises(RuntimeError):
            market_to_answer_map(mkt)


def test_pool_to_prob_cpmm1(mkt: Market, data_regression: DataRegressionFixture) -> None:
    """Test the behavior of the market to answer map utility function."""
    if mkt.market.outcomeType in Outcome.BINARY_LIKE():
        assert isinstance(mkt.market.pool, Mapping)
        assert mkt.market.p
        no = mkt.market.pool['NO']
        yes = mkt.market.pool['YES']
        p = mkt.market.p
        answer = pool_to_prob_cpmm1(yes, no, p)
        data_regression.check({'answer': answer})
    else:
        skip("Function doesn't work with this market type")


def test_pool_to_num_cpmm1(mkt: Market, data_regression: DataRegressionFixture) -> None:
    """Test the behavior of the market to answer map utility function."""
    if mkt.market.outcomeType in Outcome.PSEUDO_NUMERIC:
        assert isinstance(mkt.market.pool, Mapping)
        assert mkt.market.p
        assert mkt.market.min is not None
        assert mkt.market.max is not None
        assert mkt.market.isLogScale is not None
        no = mkt.market.pool['NO']
        yes = mkt.market.pool['YES']
        answer = pool_to_number_cpmm1(yes, no, mkt.market.p, mkt.market.min, mkt.market.max, mkt.market.isLogScale)
        data_regression.check({'answer': answer})
    else:
        skip("Function doesn't work with this market type")


def test_prob_to_num_cpmm1(mkt: Market, data_regression: DataRegressionFixture) -> None:
    """Test the behavior of the market to answer map utility function."""
    if mkt.market.outcomeType in Outcome.PSEUDO_NUMERIC:
        assert mkt.market.min is not None
        assert mkt.market.max is not None
        assert mkt.market.isLogScale is not None
        answer = prob_to_number_cpmm1(
            cast(float, mkt.market.probability or mkt.market.resolutionProbability),
            mkt.market.min,
            mkt.market.max,
            mkt.market.isLogScale
        )
        data_regression.check({'answer': answer})
    else:
        skip("Function doesn't work with this market type")


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
