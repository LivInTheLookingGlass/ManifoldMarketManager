from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pymanifold.lib import ManifoldClient

from ...util import time_cache
from .. import ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Literal

    from ...market import Market


@dataclass
class ResolveToUserProfit(ResolutionValueRule):
    """Resolve to the currently reported profit of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    @time_cache()
    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['profitCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} profit of user {self.user}.\n"


@dataclass
class ResolveToUserCreatedVolume(ResolutionValueRule):
    """Resolve to the currently reported created market volume of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    @time_cache()
    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['creatorVolumeCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
