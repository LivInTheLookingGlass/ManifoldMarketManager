from __future__ import annotations

from pickle import dumps, loads
from urllib.parse import quote

from ..market import Market
from . import manifold_vcr, mkt

assert mkt  # just need to access it so mypy doesn't complain


def assert_equality(mkt1: Market, mkt2: Market) -> None:
    """Ensure that two markets are referring to the same underlying system."""
    for attr in dir(mkt2):
        attr1 = getattr(mkt1, attr)
        attr2 = getattr(mkt2, attr)
        if callable(attr1) and callable(attr2):
            continue
        elif attr.startswith('__'):
            continue
        elif attr not in ('client', 'logger', 'market', 'event_emitter'):
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


def test_from_url(mkt: Market) -> None:
    """Make sure Markets can be grabbed by URL."""
    with manifold_vcr.use_cassette(f'test_market/fetch_by_url/{quote(mkt.id)}.yaml'):
        assert mkt.market.url
        mkt2 = Market.from_url(mkt.market.url)
    assert_equality(mkt, mkt2)


def test_from_id(mkt: Market) -> None:
    """Make sure Markets can be grabbed by ID."""
    with manifold_vcr.use_cassette(f'test_market/fetch_by_id/{quote(mkt.id)}.yaml'):
        mkt2 = Market.from_id(mkt.id)
    assert_equality(mkt, mkt2)
