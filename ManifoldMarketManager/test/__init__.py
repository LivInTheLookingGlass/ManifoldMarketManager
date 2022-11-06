"""Contain some common fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from sys import modules
from typing import Generic, TypeVar
from urllib.parse import quote

from pytest import fixture
from vcr import VCR

from ..market import Market

T = TypeVar('T')

LOCAL_FOLDER = str(Path(__file__).parent)

manifold_vcr = VCR(
    cassette_library_dir=LOCAL_FOLDER + "/fixtures/cassettes",
    record_mode="once",
    match_on=["uri", "method"],
    filter_headers=["authorization"],
    decode_compressed_response=True
)


@dataclass
class PytestRequest(Generic[T]):
    """Generic stub to represent a Pytest request."""

    param: T


def fetch_slug(slug: str) -> Market:
    """Fetch a market by slug, but cached."""
    with manifold_vcr.use_cassette(f'test_market/fetch_slug/{quote(slug)}.yaml'):
        return Market.from_slug(slug)


binary_slugs = (
    "will-the-european-union-have-an-off",
    "this-market-is-a-mirror-of-another",
)
pseudo_numeric_slugs = (
    "what-will-my-reported-profit-be-on",
    "will-the-trump-special-master-case",
)
binary_like_slugs = binary_slugs + pseudo_numeric_slugs
free_response_slugs = (
    "what-are-the-next-5-badges-well-add",
    "my-partner-and-i-are-considering-mo",
    "which-feature-of-my-market-manager",
)
multiple_choice_slugs = (
    "which-prediction-market-site-should",
)
mc_like_slugs = free_response_slugs + multiple_choice_slugs
all_slugs = binary_like_slugs + mc_like_slugs
combos = {
    "mkt": all_slugs,
    "bin_mkt": binary_slugs,
    "pn_mkt": binary_slugs,
    "cpmm1_mkt": binary_like_slugs,
    "fr_mkt": free_response_slugs,
    "mc_mkt": multiple_choice_slugs,
    "dpm2_mkt": mc_like_slugs,
}
__all__ = ['manifold_vcr', 'PytestRequest', "mkt", "bin_mkt", "pn_mkt", "cpmm1_mkt", "fr_mkt", "mc_mkt", "dpm2_mkt"]

mkt = bin_mkt = pn_mkt = cpmm1_mkt = fr_mkt = mc_mkt = dpm2_mkt = True  # get mypy to shut up

for name, params in combos.items():
    @fixture(params=params, name=name, scope='session')  # type: ignore
    def foo(request: PytestRequest[str]) -> Market:
        """Generate markets via a fixture."""
        return fetch_slug(request.param)

    foo.__name__ = name
    setattr(modules[__name__], name, foo)
