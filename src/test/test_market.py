from functools import lru_cache
from pickle import dumps, loads

from pytest import fixture, mark

from ..market import Market
from . import PytestRequest


@lru_cache(maxsize=None)
def fetch_slug(slug: str) -> Market:
    return Market.from_slug(slug)


@fixture(params=(
    "what-are-the-next-5-badges-well-add",
    "will-the-european-union-have-an-off",
    "my-partner-and-i-are-considering-mo"
))
def mkt(request: PytestRequest[str]) -> Market:
    return fetch_slug(request.param)


def assert_equality(mkt1: Market, mkt2: Market) -> None:
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


def test_get_state(mkt: Market) -> None:
    """Make sure that we are not divulging secrets."""
    state = mkt.__getstate__()
    assert getattr(state.get('client'), 'api_key', None) is None
    assert 'logger' not in state


@mark.slow
def test_pickling(mkt: Market) -> None:
    new_mkt: Market = loads(dumps(mkt))
    assert_equality(mkt, new_mkt)


@mark.slow
def test_from_id(mkt: Market) -> None:
    mkt2 = Market.from_id(mkt.id)
    assert_equality(mkt, mkt2)
