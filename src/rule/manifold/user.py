"""Contain rules that are associated with a particular Manifold user."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from attrs import define
from pymanifold.lib import ManifoldClient
from pymanifold.types import JSONDict

from ... import Rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, ClassVar, Literal

    from ...market import Market


@define(slots=False)
class ManifoldUserRule(Rule[float]):
    """Include information about what user feature you'd like to query."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"
    attr: ClassVar[str] = ""
    attr_desc: ClassVar[str] = ""

    def __init_subclass__(cls) -> None:
        """Enforce that subclasses provide an explanatory stub."""
        assert cls.attr
        assert cls.attr_desc

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, cast(JSONDict, user[self.attr])[self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current {self.field} {self.attr_desc} user {self.user}.\n"


@define(slots=False)
class ResolveToUserProfit(ManifoldUserRule):
    """Resolve to the currently reported profit of a user."""

    attr: ClassVar[str] = "profitCached"
    attr_desc: ClassVar[str] = "profit of"


@define(slots=False)
class ResolveToUserCreatedVolume(ManifoldUserRule):
    """Resolve to the currently reported created market volume of a user."""

    attr: ClassVar[str] = "creatorVolumeCached"
    attr_desc: ClassVar[str] = "market volume created by"
