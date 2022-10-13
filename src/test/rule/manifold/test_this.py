from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from pytest import raises, skip

from ....consts import Outcome
from ....market import Market
from ....rule.manifold.this import (CurrentValueRule, FibonacciValueRule, PopularValueRule, RoundValueRule,
                                    ThisMarketClosed)
from ... import manifold_vcr, mkt

assert mkt  # just need to access it so mypy doesn't complain

if TYPE_CHECKING:  # pragma: no cover
    from pytest_regressions.data_regression import DataRegressionFixture

    from ....consts import FreeResponseResolution


def test_CurentValueRule(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/this/test_CurrentValueRule/{quote(mkt.id)}.yaml'):
        obj = CurrentValueRule()
        val = obj.value(mkt)
        data_regression.check({'answer': val})


def test_FibonacciValueRule(mkt: Market, data_regression: DataRegressionFixture) -> None:
    if mkt.market.outcomeType in Outcome.MC_LIKE():
        with manifold_vcr.use_cassette(f'rule/manifold/this/test_CurrentValueRule/{quote(mkt.id)}.yaml'):
            obj = FibonacciValueRule()
            val = obj.value(mkt)
            data_regression.check({'answer': val})
    else:
        skip("Rule does not support this market type")


def test_PopularValueRule(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/this/test_CurrentValueRule/{quote(mkt.id)}.yaml'):
        if mkt.market.outcomeType in Outcome.MC_LIKE():
            answer_to_check: list[FreeResponseResolution] = []
            answer_to_check.append({})  # type: ignore
            while True:
                obj = PopularValueRule(size=len(answer_to_check))
                val = obj._value(mkt)
                if val == answer_to_check[-1]:
                    break
                answer_to_check.append(val)
            data_regression.check({'answers': answer_to_check})
        else:
            with raises(RuntimeError):
                PopularValueRule(size=1).value(mkt)


def test_RoundValueRule(mkt: Market, data_regression: DataRegressionFixture) -> None:
    if mkt.market.outcomeType in Outcome.BINARY_LIKE():
        with manifold_vcr.use_cassette(f'rule/manifold/this/test_CurrentValueRule/{quote(mkt.id)}.yaml'):
            obj = RoundValueRule()
            val = obj.value(mkt)
            data_regression.check({'answer': val})
    else:
        skip("Rule does not support this market type")


def test_ThisMarketClosed(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/this/test_CurrentValueRule/{quote(mkt.id)}.yaml'):
        obj = ThisMarketClosed()
        val = obj.value(mkt)
        data_regression.check({'answer': val})
