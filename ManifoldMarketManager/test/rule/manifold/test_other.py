from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from pytest import mark

from ....account import Account
from ....consts import Outcome
from ....market import Market
from ....rule.manifold.other import (AmplifiedOddsRule, OtherMarketClosed, OtherMarketResolved,
                                     OtherMarketUniqueTraders, OtherMarketValue)
from ....util import hash_to_randrange
from ... import cpmm1_mkt, manifold_vcr, mkt

assert mkt, cpmm1_mkt  # just need to access it so mypy doesn't complain

if TYPE_CHECKING:  # pragma: no cover
    from pytest_regressions.data_regression import DataRegressionFixture

    from ....consts import AnyResolution


def test_OtherMarketClosed(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketClosed/{quote(mkt.market.id)}.yaml'):
        obj = OtherMarketClosed(id_=mkt.market.id)
        val = obj._value(mkt, Account.from_env())
        data_regression.check({'answer': val})


def test_OtherMarketResolved(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketResolved/{quote(mkt.market.id)}.yaml'):
        obj = OtherMarketResolved(id_=mkt.market.id)
        val = obj._value(mkt, Account.from_env())
        data_regression.check({'answer': val})


def test_OtherMarketValue(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketValue/{quote(mkt.market.id)}.yaml'):
        obj: OtherMarketValue[AnyResolution] = OtherMarketValue(id_=mkt.market.id)
        val = obj._value(mkt, Account.from_env())
        data_regression.check({'answer': val})


def test_OtherMarketUniqueTraders(mkt: Market, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/other/test_OtherMarketUniqueTraders/{quote(mkt.market.id)}.yaml'):
        obj = OtherMarketUniqueTraders(id_=mkt.market.id)
        val = obj._value(mkt, Account.from_env())
        data_regression.check({'answer': val})


@mark.depends(on=('test_OtherMarketValue', ))
def test_AmplifiedOddsRule(cpmm1_mkt: Market, data_regression: DataRegressionFixture) -> None:
    mkt = cpmm1_mkt
    if mkt.market.outcomeType == Outcome.BINARY:
        filename = f'rule/manifold/other/test_AmplifiedOddsRule/{quote(mkt.market.id)}.yaml'
        with manifold_vcr.use_cassette(filename):
            obj = AmplifiedOddsRule(
                seed=filename,
                id_=mkt.market.id,
                a=hash_to_randrange(filename.encode(), 1, 129)
            )
            val = obj._value(mkt, Account.from_env())
            data_regression.check({'answer': val})
