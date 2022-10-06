from __future__ import annotations

from typing import TYPE_CHECKING, cast

from attrs import define
from pymanifold.lib import ManifoldClient

from ... import Rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, ClassVar, Literal

    from ...market import Market


@define(slots=False)
class ManifoldUserRule(Rule[float]):
    """Include information about what user feature you'd like to query."""

    user: str
    time_frame: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"
    field: ClassVar[str] = ""
    field_desc: ClassVar[str] = ""

    def __init_subclass__(cls) -> None:
        """Enforce that subclasses provide an explanatory stub."""
        assert cls.field
        assert cls.field_desc

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user[self.field][self.time_frame])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current {self.time_frame} {self.field_desc} user {self.user}.\n"


@define(slots=False)
class ResolveToUserProfit(ManifoldUserRule):
    """Resolve to the currently reported profit of a user."""

    field: ClassVar[str] = "profitCached"
    field_desc: ClassVar[str] = "profit of"


@define(slots=False)
class ResolveToUserCreatedVolume(ManifoldUserRule):
    """Resolve to the currently reported created market volume of a user."""

    field: ClassVar[str] = "creatorVolumeCached"
    field_desc: ClassVar[str] = "market volume created by"
