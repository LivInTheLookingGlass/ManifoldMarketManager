from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture, mark

from ...account import Account
from ...market import Market
from .. import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from .. import PytestRequest

# slug -> everything else
examples: dict[str, Any] = {
    'amplified-odds-100x-will-a-nuclear-4acd2868830b': {
        'market': None,
        'account': Account(ManifoldUsername='Test Case', ManifoldToken='FAKE_TOKEN'),
        'do_resolve_rules': [[
            'manifold.other.OtherMarketResolved',
            {'id_': 'jsqfBFbbIyP4X40L6VSo'}
        ]],
        'resolve_to_rules': [[
            'manifold.other.AmplifiedOddsRule',
            {
                'a': 100,
                'id_': 'jsqfBFbbIyP4X40L6VSo',
                'seed': b'6\x1b\xe9\r\xa9F\xa3\xcc\xf0\x00\x8f\xe8KC\x81d',
            }
        ]],
    },
}


@fixture(params=examples)  # type: ignore
def amplified_example(request: PytestRequest[str]) -> Market:
    with manifold_vcr.use_cassette(f'examples/amplified_odds/fetch/{request.param}.yaml'):
        ret = Market.from_dict(examples[request.param])
        # ret.client = client = get_client()
        ret.market = ret.client.get_market_by_slug(request.param)
        ret.market.isResolved = False
        return ret


@mark.depends(on=(
    "ManifoldMarketManager/test/rule/manifold/test_other.py::test_AmplifiedOddsRule",
))
def test_AmplifiedOddsMarket(amplified_example: Market) -> None:
    with manifold_vcr.use_cassette(f'examples/amplified_odds/{amplified_example.id}.yaml'):
        if amplified_example.should_resolve(Account.from_env()):
            amplified_example.resolve(Account.from_env())
        else:  # pragma: no cover
            raise RuntimeError()
