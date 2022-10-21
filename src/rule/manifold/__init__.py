"""Contain rules that reference things on Manifold Markets."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from attrs import define

from ...caching import parallel
from ...util import get_client

if TYPE_CHECKING:  # pragma: no cover
    from concurrent.futures import Future
    from typing import Optional

    from pymanifold.lib import ManifoldClient
    from pymanifold.types import Market as APIMarket

__all__ = ('this', 'other', 'user', 'ManifoldMarketMixin')


@define(slots=False)
class ManifoldMarketMixin:
    """A mixin class that holds the access to a Manifold market."""

    id_: str = ''
    slug: Optional[str] = None
    url: Optional[str] = None

    def __attrs_post_init__(self) -> None:
        """Ensure we have at least the id."""
        if hasattr(super(), '__attrs_post_init__'):
            super().__attrs_post_init__()  # type: ignore
        if self.id_:
            return
        elif self.slug:
            slug = self.slug
        else:
            slug = self.slug = cast(str, self.url).split("/")[-1]
        self.id_ = get_client().get_market_by_slug(slug).id

    def api_market(self, client: Optional[ManifoldClient] = None) -> APIMarket:
        """Return an APIMarket object associated with this rule's market."""
        if client is None:
            client = get_client()
        return client.get_market_by_id(self.id_)

    def f_api_market(self, client: Optional[ManifoldClient] = None) -> Future[APIMarket]:
        """Return a Futures which resolves to the APIMarket object associated with this rule's market."""
        return parallel(self.api_market, client)


from . import other, this, user  # noqa: E402
