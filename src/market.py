from dataclasses import dataclass, field
from enum import Enum, auto
from logging import Logger, getLogger
from math import log10
from time import time
from typing import Any, List, Mapping, Optional, Tuple, Union, cast

from pymanifold.lib import ManifoldClient
from pymanifold.types import Market as APIMarket
from requests import Response

from . import AnyResolution
from .rule import DoResolveRule, ResolutionValueRule
from .util import explain_abstract, get_client, require_env


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

    def __postinit__(self) -> None:
        """Initialize state that doesn't make sense to exist in the init."""
        self.logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    def __getstate__(self) -> Mapping[str, Any]:
        """Remove sensitive/non-serializable state before dumping to database."""
        state = self.__dict__.copy()
        del state['client']
        if 'logger' in state:
            del state['logger']
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        """Rebuild sensitive/non-serializable state after retrieving from database."""
        self.__dict__.update(state)
        self.client = get_client()
        self.market = self.client.get_market_by_id(self.market.id)
        self.__postinit__()

    @property
    def id(self) -> str:
        """Return the ID of a market as reported by Manifold."""
        return cast(str, self.market.id)

    @property
    def status(self) -> MarketStatus:
        """Return whether a market is OPEN, CLOSED, or RESOLVED."""
        if self.market.isResolved:
            return MarketStatus.RESOLVED
        elif self.market.closeTime and self.market.closeTime < time() * 1000:
            return MarketStatus.CLOSED
        return MarketStatus.OPEN

    @classmethod
    def from_slug(cls, slug: str, *args: Any, **kwargs: Any) -> 'Market':
        """Reconstruct a Market object from the market slug and other arguments."""
        api_market = get_client().get_market_by_slug(slug)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, *args: Any, **kwargs: Any) -> 'Market':
        """Reconstruct a Market object from the market ID and other arguments."""
        api_market = get_client().get_market_by_id(id)
        return cls(api_market, *args, **kwargs)

    def explain_abstract(self, **kwargs: Any) -> str:
        """Explain how the market will resolve and decide to resolve."""
        # set up potentially necessary information
        if "max_" not in kwargs:
            kwargs["max_"] = self.market.max
        if "time_rules" not in kwargs:
            kwargs["time_rules"] = self.do_resolve_rules
        if "value_rules" not in kwargs:
            kwargs["value_rules"] = self.resolve_to_rules

        return explain_abstract(**kwargs)

    def explain_specific(self) -> str:
        """Explain why the market is resolving the way that it is."""
        if self.should_resolve() is not True:
            ret = "This market is not resolving, because none of the following are true:\n"
            for rule_ in self.do_resolve_rules:
                ret += rule_.explain_specific(market=self, indent=1)
            ret += "\nWere it to resolve now, it would follow the decision tree below:\n"
        else:
            ret = "This market is resolving because of the following trigger(s):\n"
            for rule_ in self.do_resolve_rules:
                if rule_.value(self):
                    ret += rule_.explain_specific(market=self, indent=1)
            ret += "\nIt will follow the decision tree below:\n"

        ret += "- If the human operator agrees:\n"
        for rule_ in self.resolve_to_rules:
            ret += rule_.explain_specific(market=self, indent=1)
        ret += f"\nFinal Value: {self.resolve_to()}"
        return ret

    def should_resolve(self) -> bool:
        """Return whether the market should resolve, according to our rules."""
        return any(
            rule.value(self) for rule in (self.do_resolve_rules or ())
        ) and not self.market.isResolved

    def resolve_to(self) -> AnyResolution:
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

    def current_answer(self) -> Union[str, AnyResolution]:
        """Return the current top (single) answer."""
        # TODO: move these behaviors to a rule class
        if self.market.outcomeType == "BINARY":
            return f"{100 * self.market.probability}%"
        elif self.market.outcomeType == "PSEUDO_NUMERIC":
            pno = self.market.p * self.market.pool['NO']
            probability = (pno / ((1 - self.market.p) * self.market.pool['YES'] + pno))
            start = float(self.market.min or 0)
            end = float(self.market.max or 0)
            ret: float
            if self.market.isLogScale:
                logValue = log10(end - start + 1) * probability
                ret = max(start, min(end, 10**logValue + start - 1))
            else:
                ret = max(start, min(end, start + (end - start) * probability))
            return ret
        elif self.market.outcomeType == "FREE_RESPONSE":
            return {idx: x['probability'] for idx, x in enumerate(self.market.answers)}
        elif self.market.outcomeType == "MULTIPLE_CHOICE":
            total = sum(self.market.pool.values())
            return {x: shares / total for x, shares in self.market.pool.items()}
        else:
            raise NotImplementedError(self.market.outcomeType)

    @require_env("ManifoldAPIKey")
    def resolve(self, override: Optional[AnyResolution] = None) -> Response:
        """Resolve this market according to our resolution rules.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        _override: Union[AnyResolution, Tuple[float, float]]
        if override is None:
            _override = self.resolve_to()
        else:
            _override = override
        if self.market.outcomeType == "PSEUDO_NUMERIC":
            start = float(self.market.min or 0)
            end = float(self.market.max or 0)
            if not isinstance(_override, (int, float)):
                raise TypeError()
            if self.market.isLogScale:
                _override = (_override, log10(_override - start + 1) / log10(end - start + 1) * 100)
            else:
                _override = (_override, (_override - start) / (end - start) * 100)
        if self.market.outcomeType in ("FREE_RESPONSE", "MULTIPLE_CHOICE"):
            if not isinstance(_override, Mapping):
                raise TypeError()
            # if self.market.answers is not None:
            #     new_override = {}
            #     for idx, weight in override.items():
            #         new_override[self.market.answers[idx]['id']] = weight
            #     override = new_override
            new_override = {}
            for idx, weight in _override.items():
                new_override[int(idx)] = weight
            _override = new_override
        ret: Response = self.client.resolve_market(self.market, _override)
        if ret.status_code < 300:
            self.logger.info("I was resolved")
            self.market.isResolved = True
        return ret

    @require_env("ManifoldAPIKey")
    def cancel(self) -> Response:
        """Cancel this market.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        ret: Response = self.client.cancel_market(self.market)
        if ret.status_code < 300:
            self.logger.info("I was cancelled")
            self.market.isResolved = True
        return ret
