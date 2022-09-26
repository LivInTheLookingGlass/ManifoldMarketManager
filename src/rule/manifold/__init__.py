from dataclasses import dataclass
from typing import Optional, cast

from pymanifold.lib import ManifoldClient
from pymanifold.types import Market as APIMarket

from ...util import get_client

__all__ = ('time', 'value', 'ManifoldMarketMixin')


@dataclass
class ManifoldMarketMixin:
    id_: Optional[str] = None
    slug: Optional[str] = None
    url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.id_:
            return
        elif self.slug:
            slug = self.slug
        else:
            slug = cast(str, self.url).split("/")[-1]
        self.id_ = get_client().get_market_by_slug(slug).id

    def api_market(self, client: Optional[ManifoldClient] = None) -> APIMarket:
        if client is None:
            client = get_client()
        return client.get_market_by_id(self.id_)


from . import time, value  # noqa: E402
