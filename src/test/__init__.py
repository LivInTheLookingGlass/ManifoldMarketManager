from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass
class PytestRequest(Generic[T]):
    """Generic stub to represent a Pytest request."""

    param: T
