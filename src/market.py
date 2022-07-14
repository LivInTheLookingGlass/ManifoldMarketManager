from dataclasses import dataclass
from typing import Optional, List, Union

from pymanifold import ManifoldClient, Market as APIMarket


class Rule:
    def value(self, market: 'Market'):
        ...


@dataclass
class Market:
    client: ManifoldClient
    market: APIMarket
    do_resolve_rules: Optional[List[Rule]] = None
    resolve_to_rules: Optional[List[Rule]] = None

    @property
    def id(self):
        return self.market.id

    @classmethod
    def from_slug(cls, slug: str, client: ManifoldClient, *args, **kwargs):
        api_market = client.get_market_by_slug(slug)
        return cls(client, api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, client: ManifoldClient, *args, **kwargs):
        api_market = client.get_market_by_id(id)
        return cls(client, api_market, *args, **kwargs)

    def should_resolve(self) -> bool:
        return any(
            rule.value(self) for rule in (self.do_resolve_rules or ())
        ) and not self.market.isResolved

    def resolve_to(self) -> Union[bool, int, str]:
        chosen = None
        for rule in (self.resolve_to_rules or ()):
            if (chosen := rule.value(self)) is not None:
                break
        if chosen is not None:
            return chosen
        if self.market.probability is not None:
            return bool(round(self.market.probability))
        return max(self.market.answers, key=lambda x: x['probability'])

    def resolve(self):
        raise NotImplementedError("TODO: PyManifold does not have an implementation yet")