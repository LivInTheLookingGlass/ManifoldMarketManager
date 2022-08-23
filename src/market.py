from dataclasses import dataclass, field
from enum import auto, Enum
from functools import lru_cache
from logging import getLogger, Logger
from math import log10
from os import getenv
from time import time
from typing import Any, Dict, List, Union

from pymanifold import ManifoldClient
from pymanifold.types import Market as APIMarket

from . import require_env
from .rule import DoResolveRule, ResolutionValueRule


@lru_cache
@require_env("ManifoldAPIKey")
def get_client() -> ManifoldClient:
    """Return a (possibly non-unique) Manifold client."""
    return ManifoldClient(getenv("ManifoldAPIKey"))


class MarketStatus(Enum):
    """Represent the status of a market at a high level."""

    OPEN = auto()
    CLOSED = auto()
    RESOLVED = auto()


@dataclass
class Market:
    """Represent a market and its corresponding rules."""

    market: APIMarket
    client: ManifoldClient = field(default_factory=get_client)
    notes: str = field(default='')
    do_resolve_rules: List[DoResolveRule] = field(default_factory=list)
    resolve_to_rules: List[ResolutionValueRule] = field(default_factory=list)
    logger: Logger = field(init=False, default=None, repr=False)  # type: ignore[assignment]

    def __postinit__(self):
        """Initialize state that doesn't make sense to exist in the init."""
        self.logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    def __getstate__(self):
        """Remove sensitive/non-serializable state before dumping to database."""
        state = self.__dict__.copy()
        del state['client']
        if 'logger' in state:
            del state['logger']
        return state

    def __setstate__(self, state):
        """Rebuild sensitive/non-serializable state after retrieving from database."""
        self.__dict__.update(state)
        self.client = get_client()
        self.market = self.client.get_market_by_id(self.market.id)
        self.__postinit__()
        # if not self.resolve_to_rules:
        #     match self.market.outcomeType:
        #         case "BINARY":
        #             self.resolve_to_rules.append(RoundValueRule())
        #         case "PSEUDO_NUMERIC":
        #             self.resolve_to_rules.append(CurrentValueRule())
        #         case "FREE_RESONSE" | "MULTIPLE_CHOICE":
        #             self.resolve_to_rules.append(PopularValueRule())

    @property
    def id(self):
        """Return the ID of a market as reported by Manifold."""
        return self.market.id

    @property
    def status(self) -> MarketStatus:
        """Return whether a market is OPEN, CLOSED, or RESOLVED."""
        if self.market.isResolved:
            return MarketStatus.RESOLVED
        elif self.market.closeTime and self.market.closeTime < time() * 1000:
            return MarketStatus.CLOSED
        return MarketStatus.OPEN

    @classmethod
    def from_slug(cls, slug: str, *args, **kwargs):
        """Reconstruct a Market object from the market slug and other arguments."""
        api_market = get_client().get_market_by_slug(slug)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, *args, **kwargs):
        """Reconstruct a Market object from the market ID and other arguments."""
        api_market = get_client().get_market_by_id(id)
        return cls(api_market, *args, **kwargs)

    def explain_abstract(self, **kwargs) -> str:
        """Explain how the market will resolve and decide to resolve."""
        # set up potentially necessary information
        if "max_" not in kwargs:
            kwargs["max_"] = self.market.max

        # assemble the market contract
        ret = ""
        for rule in self.do_resolve_rules:
            ret += rule.explain_abstract(**kwargs)
        ret += "\nIt will resolve based on the following decision tree:\n"
        for rule in self.resolve_to_rules:
            ret += rule.explain_abstract(**kwargs)
        ret += (
            "\nNote that the bot operator reserves the right to resolve contrary to the purely automated rules to "
            "preserve the spirit of the market."
            "\n\n"
            "The operator also reserves the right to trade on this market unless otherwise specified. Even if "
            "otherwise specified, the operator reserves the right to buy shares for subsidy or to trade for the "
            "purposes of cashing out liquidity.\n"
        )
        return ret

    def explain_specific(self) -> str:
        """Explain why the market is resolving the way that it is."""
        ...

    def should_resolve(self) -> bool:
        """Return whether the market should resolve, according to our rules."""
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
            if (chosen := rule.value(self, format=self.market.outcomeType)) is not None:
                break
        if chosen is None:
            raise RuntimeError()
        return chosen

    def current_answer(self) -> Union[str, int, float, Dict[Union[str, int], float]]:
        """Return the current top (single) answer."""
        # TODO: move these behaviors to a rule class
        if self.market.outcomeType == "BINARY":
            return f"{100 * self.market.probability}%"
        elif self.market.outcomeType == "PSEUDO_NUMERIC":
            pno = self.market.p * self.market.pool['NO']
            probability = (pno / ((1 - self.market.p) * self.market.pool['YES'] + pno))
            start = float(self.market.min or 0)
            end = float(self.market.max or 0)
            if self.market.isLogScale:
                logValue = log10(end - start + 1) * probability
                return max(start, min(end, 10**logValue + start - 1))
            else:
                return max(start, min(end, start + (end - start) * probability))
        elif self.market.outcomeType == "FREE_RESPONSE":
            return {idx: x['probability'] for idx, x in enumerate(self.market.answers)}
        elif self.market.outcomeType == "MULTIPLE_CHOICE":
            total = sum(self.market.pool.values())
            return {x: shares / total for x, shares in self.market.pool.items()}
        else:
            raise NotImplementedError(self.market.outcomeType)

    @require_env("ManifoldAPIKey")
    def resolve(self, override=None):
        """Resolve this market according to our resolution rules.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        if override is None:
            override = self.resolve_to()
        if self.market.outcomeType == "PSEUDO_NUMERIC":
            start = float(self.market.min or 0)
            end = float(self.market.max or 0)
            if self.market.isLogScale:
                override = (override, log10(override - start + 1) / log10(end - start + 1) * 100)
            else:
                override = (override, (override - start) / (end - start) * 100)
        ret = self.client.resolve_market(self.market, override)
        if ret.status_code < 300:
            self.logger.info("I was resolved")
            self.market.isResolved = True
        return ret

    @require_env("ManifoldAPIKey")
    def cancel(self):
        """Cancel this market.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        ret = self.client.cancel_market(self.market)
        if ret.status_code < 300:
            self.logger.info("I was cancelled")
            self.market.isResolved = True
        return ret
