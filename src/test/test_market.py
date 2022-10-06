from __future__ import annotations

from os import putenv
from pickle import dumps, loads
from typing import TYPE_CHECKING
from urllib.parse import quote

from pytest import fixture

from ..market import Market
from . import manifold_vcr

if TYPE_CHECKING:  # pragma: no cover
    from . import PytestRequest

putenv('ManifoldAPIKey', 'fake_api_key')


def fetch_slug(slug: str) -> Market:
    """Fetch a market by slug, but cached."""
    with manifold_vcr.use_cassette(f'test_market/fetch_slug/{quote(slug)}.yaml'):
        return Market.from_slug(slug)


@fixture(params=(
    "what-are-the-next-5-badges-well-add",
    "will-the-european-union-have-an-off",
    "my-partner-and-i-are-considering-mo"
))
def mkt(request: PytestRequest[str]) -> Market:
    """Generate markets via a fixture."""
    return fetch_slug(request.param)


def assert_equality(mkt1: Market, mkt2: Market) -> None:
    """Ensure that two markets are referring to the same underlying system."""
    for attr in dir(mkt2):
        attr1 = getattr(mkt1, attr)
        attr2 = getattr(mkt2, attr)
        if callable(attr1) and callable(attr2):
            continue
        elif attr.startswith('__'):
            continue
        elif attr not in ('client', 'logger', 'market'):
            assert attr1 == attr2
        elif attr == 'market':
            assert mkt1.market.id == mkt2.market.id


def test_repr(mkt: Market) -> None:
    """Make sure that repr does not error on common cases."""
    assert repr(mkt)


def test_get_state(mkt: Market) -> None:
    """Make sure that we are not divulging secrets."""
    state = mkt.__getstate__()
    assert getattr(state.get('client'), 'api_key', None) is None
    assert 'logger' not in state


def test_pickling(mkt: Market) -> None:
    """Make sure Markets can be dumped to disk and reloaded."""
    with manifold_vcr.use_cassette(f'test_market/pickle_load/{quote(mkt.id)}.yaml'):
        new_mkt: Market = loads(dumps(mkt))
    assert_equality(mkt, new_mkt)


def test_from_id(mkt: Market) -> None:
    """Make sure Markets can be grabbed by ID."""
    with manifold_vcr.use_cassette(f'test_market/fetch_by_id/{quote(mkt.id)}.yaml'):
        mkt2 = Market.from_id(mkt.id)
    assert_equality(mkt, mkt2)
