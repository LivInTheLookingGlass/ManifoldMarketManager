from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from pytest import skip

from ....consts import Outcome
from ....market import Market
from ....rule.manifold.other import AmplifiedOddsRule, OtherMarketClosed, OtherMarketResolved, OtherMarketValue
from ....util import hash_to_randrange
from ... import manifold_vcr, mkt

assert mkt  # just need to access it so mypy doesn't complain

if TYPE_CHECKING:  # pragma: no cover
    from pytest_regressions.data_regression import DataRegressionFixture

    from ....consts import AnyResolution


def test_OtherMarketClosed(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketClosed/{quote(mkt.id)}.yaml'):
        obj = OtherMarketClosed(id_=mkt.id)
        val = obj._value(mkt)
        data_regression.check({'answer': val})


def test_OtherMarketResolved(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketResolved/{quote(mkt.id)}.yaml'):
        obj = OtherMarketResolved(id_=mkt.id)
        val = obj._value(mkt)
        data_regression.check({'answer': val})


def test_OtherMarketValue(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketValue/{quote(mkt.id)}.yaml'):
        obj: OtherMarketValue[AnyResolution] = OtherMarketValue(id_=mkt.id)
        val = obj._value(mkt)
        data_regression.check({'answer': val})


def test_AmplifiedOddsRule(mkt: Market, data_regression: DataRegressionFixture) -> None:
    if mkt.market.outcomeType == Outcome.BINARY:
        filename = f'rule/manifold/other/test_AmplifiedOddsRule/{quote(mkt.id)}.yaml'
        with manifold_vcr.use_cassette(filename):
            obj = AmplifiedOddsRule(
                seed=filename,
                id_=mkt.id,
                a=hash_to_randrange(filename.encode(), 1, 129)
            )
            val = obj._value(mkt)
            data_regression.check({'answer': val})
    else:
        skip("Rule does not support this market type")
