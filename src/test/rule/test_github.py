from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING

from pytest import fixture

from ...market import Market
from ...rule.github import ResolveToPR, ResolveToPRDelta, ResolveWithPR, login, unauth_login
from .. import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from pytest_regressions.data_regression import DataRegressionFixture

    from .. import PytestRequest

issues = [
    ("LivInTheLookingGlass", "ManifoldMarketManager", 2),
    ("LivInTheLookingGlass", "ManifoldMarketManager", 3),
    ("LivInTheLookingGlass", "ManifoldMarketManager", 4),
    ("LivInTheLookingGlass", "ManifoldMarketManager", 14),
    ("LivInTheLookingGlass", "ManifoldMarketManager", 15),
    ("bcongdon", "PyManifold", 1),
    ("bcongdon", "PyManifold", 2),
    ("bcongdon", "PyManifold", 3),
]


@fixture(params=issues, ids=["%s - %s - %d" % tup for tup in issues])  # type: ignore
def pr_tup(request: PytestRequest[tuple[str, str, int]]) -> tuple[str, str, int]:
    """Generate markets via a fixture."""
    return request.param


@manifold_vcr.use_cassette()  # type: ignore
def test_auth_login() -> None:
    login()


@manifold_vcr.use_cassette()  # type: ignore
def test_unauth_login() -> None:
    unauth_login()


def test_ResolveWithPR(
    pr_tup: tuple[str, str, int], data_regression: DataRegressionFixture
) -> None:
    owner, repo, number = pr_tup
    with manifold_vcr.use_cassette(f'rule/github/test_ResolveWithPR/{owner}/{repo}/pr_{number}.yaml'):
        obj = ResolveWithPR(*pr_tup)
        mkt: Market = None  # type: ignore[assignment]
        data_regression.check({'answer': obj.value(mkt, refresh=True)})
        desc = obj.explain_abstract()
        for arg in pr_tup:
            assert str(arg) in desc


def test_ResolveToPR(
    pr_tup: tuple[str, str, int], data_regression: DataRegressionFixture
) -> None:
    owner, repo, number = pr_tup
    with manifold_vcr.use_cassette(f'rule/github/test_ResolveToPR/{owner}/{repo}/pr_{number}.yaml'):
        obj = ResolveToPR(*pr_tup)
        mkt: Market = None  # type: ignore[assignment]
        data_regression.check({'answer': obj.value(mkt, refresh=True)})
        desc = obj.explain_abstract()
        for arg in pr_tup:
            assert str(arg) in desc


def test_ResolveToPRDelta(
    pr_tup: tuple[str, str, int], data_regression: DataRegressionFixture
) -> None:
    owner, repo, number = pr_tup
    mkt: Market = Namespace()  # type: ignore[assignment]
    mkt.market = Namespace()  # type: ignore
    mkt.market.max = 1000
    mkt.do_resolve_rules = []
    mkt.resolve_to_rules = []
    with manifold_vcr.use_cassette(f'rule/github/test_ResolveToPRDelta/{owner}/{repo}/pr_{number}.yaml'):
        created_at = login().issue(*pr_tup).created_at
        obj = ResolveToPRDelta(*pr_tup, start=created_at)
        data_regression.check({'answer': obj.value(mkt, refresh=True)})
        desc = obj.explain_abstract(max_=1000)
        for arg in pr_tup:
            assert str(arg) in desc
