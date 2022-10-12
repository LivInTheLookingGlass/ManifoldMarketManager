"""Contain some common fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


@fixture(params=(
    "what-are-the-next-5-badges-well-add",
    "will-the-european-union-have-an-off",
    "my-partner-and-i-are-considering-mo",
    "which-feature-of-my-market-manager",
    "which-prediction-market-site-should",
    "what-will-my-reported-profit-be-on",
    "will-the-trump-special-master-case",
    "this-market-is-a-mirror-of-another",
))  # type: ignore
def mkt(request: PytestRequest[str]) -> Market:
    """Generate markets via a fixture."""
    return fetch_slug(request.param)
