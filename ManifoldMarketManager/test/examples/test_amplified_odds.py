from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture, mark

from ...account import Account
from ...market import Market
from ...util import get_client
from .. import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from .. import PytestRequest

account = Account(ManifoldUsername='Test Case', ManifoldToken='FAKE_TOKEN')

# slug -> everything else
examples: dict[str, Any] = {
    'amplified-odds-100x-will-a-nuclear-4acd2868830b': {
        'market': None,
        'client': get_client(account),
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
    with manifold_vcr.use_cassette(f'examples/amplified_odds/{amplified_example.market.id}.yaml'):
        if amplified_example.should_resolve(account):
            amplified_example.resolve(account)
        else:  # pragma: no cover
            raise RuntimeError()
