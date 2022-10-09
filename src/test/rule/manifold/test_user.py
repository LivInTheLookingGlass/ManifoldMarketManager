from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pytest import fixture

from ....market import Market
from ....rule.manifold.user import ResolveToUserCreatedVolume, ResolveToUserProfit
from ... import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from typing import Literal

    from ... import PytestRequest

    FieldType = Literal["allTime", "daily", "weekly", "monthly"]


@fixture(params=["LivInTheLookingGlass", "v"])
def manifold_user(request: PytestRequest[str]) -> str:
    return request.param


@fixture(params=["allTime", "daily", "weekly", "monthly"])
def field(request: PytestRequest[FieldType]) -> FieldType:
    return request.param


def test_user_profit(manifold_user: str, field: FieldType) -> None:
    expected: dict[str, dict[str, float]] = {
        "LivInTheLookingGlass": {
            "allTime": 6131.776489376594,
            "daily": 177.9272442400179,
            "weekly": 496.933697342356,
            "monthly": 2377.20519440705,
        },
        "v": {
            "allTime": 23412.99914548799,
            "daily": 4619.0476158665515,
            "weekly": 8063.125743897224,
            "monthly": 22931.496516780604,
        },
    }
    with manifold_vcr.use_cassette(f'rule/manifold/test_user_profit/{manifold_user}/{field}.yaml'):
        obj = ResolveToUserProfit(manifold_user, field)
        print(obj._value(cast(Market, None)))
        assert obj._value(cast(Market, None)) == expected[manifold_user][field]


def test_user_market_volume(manifold_user: str, field: FieldType) -> None:
    expected: dict[str, dict[str, float]] = {
        "LivInTheLookingGlass": {
            "allTime": 62890.969107217374,
            "daily": 790.9647473532227,
            "weekly": 4484.343023585168,
            "monthly": 12540.906372343215,
        },
        "v": {
            "allTime": 0,
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
        },
    }
    with manifold_vcr.use_cassette(f'rule/manifold/test_user_volume/{manifold_user}/{field}.yaml'):
        obj = ResolveToUserCreatedVolume(manifold_user, field)
        print(obj._value(cast(Market, None)))
        assert obj._value(cast(Market, None)) == expected[manifold_user][field]
