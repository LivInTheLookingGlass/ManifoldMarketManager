from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING

from .. import DoResolveRule
from . import ManifoldMarketMixin

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ...market import Market


class ThisMarketClosed(DoResolveRule):
    def _value(self, market: Market) -> bool:
        return market.market.closeTime < time() * 1000

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves true iff this market is closed.\n"


@dataclass
class OtherMarketClosed(DoResolveRule, ManifoldMarketMixin):
    def _value(self, market: Market) -> bool:
        return self.api_market().closeTime < time() * 1000

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves true iff `{self.id_}` is closed ({self.api_market().question}).\n"


@dataclass
class OtherMarketResolved(DoResolveRule, ManifoldMarketMixin):
    def _value(self, market: Market) -> bool:
        return bool(self.api_market().isResolved)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves true iff `{self.id_}` is resolved ({self.api_market().question}).\n"
