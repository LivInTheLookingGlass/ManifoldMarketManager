from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pytest import fixture

from ....consts import FIELDS
from ....market import Market
from ....rule.manifold.user import ResolveToUserCreatedVolume, ResolveToUserProfit
from ... import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from pytest_regressions.data_regression import DataRegressionFixture

    from ....consts import FieldType
    from ... import PytestRequest


@fixture(params=["LivInTheLookingGlass", "v"])
def manifold_user(request: PytestRequest[str]) -> str:
    return request.param


@fixture(params=FIELDS)
def field(request: PytestRequest[FieldType]) -> FieldType:
    return request.param


def test_user_profit(manifold_user: str, field: FieldType, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/test_user_profit/{manifold_user}/{field}.yaml'):
        obj = ResolveToUserProfit(manifold_user, field)
        val = obj._value(cast(Market, None))
        data_regression.check({'answer': val})


def test_user_market_volume(manifold_user: str, field: FieldType, data_regression: DataRegressionFixture) -> None:
    with manifold_vcr.use_cassette(f'rule/manifold/test_user_volume/{manifold_user}/{field}.yaml'):
        obj = ResolveToUserCreatedVolume(manifold_user, field)
        val = obj._value(cast(Market, None))
        data_regression.check({'answer': val})
