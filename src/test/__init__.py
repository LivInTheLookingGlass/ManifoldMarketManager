from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from vcr import VCR

T = TypeVar('T')

LOCAL_FOLDER = str(Path(__file__).parent)

manifold_vcr = VCR(
    cassette_library_dir=LOCAL_FOLDER + "/fixtures/cassettes",
    record_mode="once",
    match_on=["uri", "method"],
    filter_headers=["authorization"],
)


@dataclass
class PytestRequest(Generic[T]):
    """Generic stub to represent a Pytest request."""

    param: T
