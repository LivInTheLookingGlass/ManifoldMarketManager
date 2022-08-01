from dataclasses import dataclass, field
from enum import auto, Enum
from functools import lru_cache
from math import log10
from os import getenv
from time import time
from typing import Any, Dict, List, Optional, Union

from pymanifold import ManifoldClient
from pymanifold.types import DictDeserializable, Market as APIMarket

from .rule import DoResolveRule, ResolutionValueRule


class MarketStatus(Enum):
    OPEN = auto()
    CLOSED = auto()
    RESOLVED = auto()


@lru_cache
def get_client() -> ManifoldClient:
    return ManifoldClient(getenv("ManifoldAPIKey"))


@dataclass
class Market(DictDeserializable):
    market: APIMarket
    client: ManifoldClient = field(default_factory=get_client)
    notes: str = field(default='')
    do_resolve_rules: List[DoResolveRule] = field(default_factory=list)
    resolve_to_rules: List[ResolutionValueRule] = field(default_factory=list)
    min: Optional[float] = None
    max: Optional[float] = None
    isLogScale: Optional[bool] = None

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['client']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.client = get_client()
        self.market = self.client.get_market_by_id(self.market.id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "notes": self.notes,
            "do_resolve_rules": self.do_resolve_rules,
            "resolve_to_rules": self.resolve_to_rules,
            "min": self.min,
            "max": self.max,
            "isLogScale": self.isLogScale,
        }

    @property
    def id(self):
        return self.market.id

    @property
    def status(self) -> MarketStatus:
        if self.market.isResolved:
            return MarketStatus.RESOLVED
        elif self.market.closeTime and self.market.closeTime < time() * 1000:
            return MarketStatus.CLOSED
        return MarketStatus.OPEN

    @classmethod
    def from_slug(cls, slug: str, *args, **kwargs):
        api_market = get_client().get_market_by_slug(slug)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, *args, **kwargs):
        api_market = get_client().get_market_by_id(id)
        return cls(api_market, *args, **kwargs)

    def should_resolve(self) -> bool:
        return any(
            rule.value(self) for rule in (self.do_resolve_rules or ())
        ) and not self.market.isResolved

    def resolve_to(self) -> Union[int, float, str, Dict[int, float], Dict[str, Any]]:
        """Select a value to be resolved to.

        This is done by iterating through a series of Rules, each of which have
        opportunity to recommend a value. The first resolved value is resolved to.

        Binary markets must return a float between 0 and 100.
        Numeric markets must return a float in its correct range.
        Free response markets must resolve to either a single index integer or
         a mapping of indices to weights.
        Any rule may return "CANCEL" to instead refund all orders.
        """
        chosen = None
        for rule in (self.resolve_to_rules or ()):
            if (chosen := rule.value(self)) is not None:
                break
        if chosen is not None:
            return chosen
        return self.current_answer()

    def current_answer(self) -> Union[int, float, Dict[str, Any]]:
        if self.market.outcomeType == "BINARY":
                return bool(round(self.market.probability))
        elif self.market.outcomeType == "PSEUDO_NUMERIC":
                # import pdb; pdb.set_trace()
                pno = self.market.p * self.market.pool['NO']
                probability = (pno / ((1 - self.market.p) * self.market.pool['YES'] + pno))
            start = cast(float, self.min)
            end = cast(float, self.max)
                if self.market.isLogScale:
                logValue = log10(end - start + 1) * probability
                return max(start, min(end, 10**logValue + start - 1))
                else:
                return max(start, min(end, start + (end - start) * probability))
        elif self.market.outcomeType == "FREE_RESPONSE":
                return max(self.market.answers, key=lambda x: x['probability'])
        else:
                raise NotImplementedError()

    def resolve(self):
        """Resolves this market according to our resolution rules.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        ret = self.client.resolve_market(self.market, self.resolve_to())
        if ret.status_code < 300:
            self.market.isResolved = True
        return ret
