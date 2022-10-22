"""Contains the Market class, which associates Rules with a market on Manifold."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from logging import getLogger
from threading import Lock
from time import time
from typing import TYPE_CHECKING, cast

from pyee import EventEmitter
from pyee.cls import evented

from .caching import parallel
from .consts import EnvironmentVariable, MarketStatus, Outcome
from .rule import get_rule
from .util import DictDeserializable, explain_abstract, get_client, require_env, round_sig_figs

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger
    from typing import Any, Mapping, Optional, Sequence

    from pymanifold.lib import ManifoldClient
    from pymanifold.types import Market as APIMarket
    from requests import Response

    from . import Rule
    from .consts import AnyResolution
    from .util import ModJSONDict


@evented
@dataclass
class Market(DictDeserializable):
    """Represent a market and its corresponding rules.

    Events
    ======
    before_check(market: Market):
    after_check(market: Market):
        Called before/after a market is checked. Please don't put anything intensive in here.

    before_create(market: Market):
    after_create(market: Market):
        Called before/after a market is created.

    before_resolve(market: Market, outcome: AnyResolution):
    after_resolve(market: Market, outcome: AnyResolution, response: Response):
        Called before/after a market is resolved. Please don't put anything intensive in here.

    before_remove(market: Market):
    after_remove(market: Market):
        Called before/after a market is removed from the database.
    """

    market: APIMarket = field(repr=False, compare=False)
    client: ManifoldClient = field(default_factory=get_client, repr=False, compare=False)
    notes: str = field(default='')
    do_resolve_rules: list[Rule[Optional[bool]]] = field(default_factory=list)
    resolve_to_rules: list[Rule[AnyResolution]] = field(default_factory=list)
    logger: Logger = field(init=False, default=None, hash=False, repr=False)  # type: ignore[assignment]
    event_emitter: EventEmitter = field(init=False, default_factory=EventEmitter, hash=False, repr=False)

    def __hash__(self) -> int:
        """Hack to allow markets as dict keys."""
        return hash((Market, id(self)))

    def __repr__(self) -> str:
        """Create a representation of this market using the `Market.from_id()` constructor."""
        do_resolve_rules = self.do_resolve_rules
        resolve_to_rules = self.resolve_to_rules
        notes = self.notes
        return f"Market.from_id({self.market.id!r}, {do_resolve_rules = !r}, {resolve_to_rules = !r}, {notes = !r})"

    def __post_init__(self) -> None:
        """Initialize state that doesn't make sense to exist in the init."""
        if self._after_resolve not in self.event_emitter.listeners('after_resolve'):
            self.event_emitter.add_listener('after_resolve', self._after_resolve)
        self.logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    def __getstate__(self) -> Mapping[str, Any]:
        """Remove sensitive/non-serializable state before dumping to database."""
        state = self.__dict__.copy()
        del state['client']
        if 'logger' in state:
            del state['logger']
        state['event_emitter'] = copy(state['event_emitter'])
        del state['event_emitter']._lock
        assert self.event_emitter._lock
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        """Rebuild sensitive/non-serializable state after retrieving from database."""
        self.__dict__.update(state)
        self.client = get_client()
        self.market = self.client.get_market_by_id(self.market.id)
        if not hasattr(self, "event_emitter"):
            self.event_emitter = EventEmitter()
        self.event_emitter._lock = Lock()
        self.__post_init__()

    @property
    def id(self) -> str:
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
    def from_url(cls, url: str, *args: Any, **kwargs: Any) -> Market:
        """Reconstruct a Market object from the market url and other arguments."""
        api_market = get_client().get_market_by_url(url)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_slug(cls, slug: str, *args: Any, **kwargs: Any) -> Market:
        """Reconstruct a Market object from the market slug and other arguments."""
        api_market = get_client().get_market_by_slug(slug)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, *args: Any, **kwargs: Any) -> Market:
        """Reconstruct a Market object from the market ID and other arguments."""
        api_market = get_client().get_market_by_id(id)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_dict(cls, env: ModJSONDict) -> Market:
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        for name in ("do_resolve_rules", "resolve_to_rules"):
            arr: Sequence[tuple[str, ModJSONDict]] = env.get(name, [])  # type: ignore[assignment]
            rules: list[None | Rule[Any]] = [None] * len(arr)
            for idx, (type_, kwargs) in enumerate(arr):
                rules[idx] = get_rule(type_).from_dict(kwargs)
            env_copy[name] = rules
        return super().from_dict(env_copy)

    def _after_resolve(self, market: Market, outcome: AnyResolution, response: Response) -> None:
        self.client.create_comment(self.market, self.explain_specific(), mode='markdown')

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

    def explain_specific(self, sig_figs: int = 4) -> str:
        """Explain why the market is resolving the way that it is."""
        shim = ""
        rule_: Rule[Any]
        for rule_ in self.do_resolve_rules:
            shim += rule_.explain_specific(market=self, indent=1, sig_figs=sig_figs)
        if not (self.market.isResolved or self.should_resolve()):
            ret = (f"This market is not resolving, because none of the following are true:\n{shim}\nWere it to "
                   "resolve now, it would follow the decision tree below:\n")
        else:
            ret = (f"This market is resolving because of the following trigger(s):\n{shim}\nIt will follow the "
                   "decision tree below:\n")
        ret += "- If the human operator agrees:\n"
        for rule_ in self.resolve_to_rules:
            ret += rule_.explain_specific(market=self, indent=1, sig_figs=sig_figs)
        ret += "\nFinal Value: "
        ret += self.__format_resolve_to(sig_figs)
        return ret

    def __format_resolve_to(self, sig_figs: int) -> str:
        val = self.resolve_to()
        if val == "CANCEL":
            ret = "CANCEL"
        elif isinstance(val, bool) or self.market.outcomeType == Outcome.BINARY:
            defaults: dict[AnyResolution, str] = {
                True: "YES", 100: "YES", 100.0: "YES",
                False: "NO"
            }
            if val in defaults:
                ret = defaults[val]
            else:
                ret = round_sig_figs(cast(float, val), sig_figs) + "%"
        elif self.market.outcomeType in Outcome.MC_LIKE():
            assert not isinstance(val, (float, str))
            ret = "{"
            total = sum(val.values())
            for idx, (key, weight) in enumerate(val.items()):
                ret += ", " * bool(idx)
                ret += f"{key}: {round_sig_figs(weight * 100 / total, sig_figs)}%"
            ret += "}"
        else:
            ret = str(val)
        return ret

    def should_resolve(self) -> bool:
        """Return whether the market should resolve, according to our rules."""
        futures = [parallel(rule.value, self) for rule in (self.do_resolve_rules or ())]
        return any(future.result() for future in futures) and not self.market.isResolved

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
        assert self.market.outcomeType != "NUMERIC"
        chosen = None
        futures = [parallel(rule.value, self, format=self.market.outcomeType) for rule in (self.resolve_to_rules or ())]
        for f_rule in futures:
            chosen = f_rule.result()
            if chosen is not None:
                break
        if chosen is None:
            raise RuntimeError()
        return chosen

    def current_answer(self) -> AnyResolution:
        """Return the current market consensus."""
        from .rule.manifold.this import CurrentValueRule
        assert self.market.outcomeType != "NUMERIC"
        return CurrentValueRule().value(self, format=self.market.outcomeType)

    @require_env(EnvironmentVariable.ManifoldAPIKey)
    def resolve(self, override: Optional[AnyResolution] = None) -> Response:
        """Resolve this market according to our resolution rules.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        _override: AnyResolution | tuple[float, float]
        if override is None:
            _override = self.resolve_to()
        else:
            _override = override
        if _override == "CANCEL":
            return self.cancel()

        if self.market.outcomeType in Outcome.MC_LIKE():
            if not isinstance(_override, Mapping):
                raise TypeError()
            _override = {int(id_): weight for id_, weight in _override.items()}

        self.event_emitter.emit('before_resolve', self, _override)
        ret: Response = self.client.resolve_market(self.market, _override)
        ret.raise_for_status()
        self.logger.info("I was resolved")
        self.market.isResolved = True
        self.event_emitter.emit('after_resolve', self, _override, ret)
        return ret

    @require_env(EnvironmentVariable.ManifoldAPIKey)
    def cancel(self) -> Response:
        """Cancel this market.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        ret: Response = self.client.cancel_market(self.market)
        ret.raise_for_status()
        self.logger.info("I was cancelled")
        self.market.isResolved = True
        return ret

    def on(self, *args, **kwargs):  # type: ignore
        """Register an event with EventEmitter."""
        return self.event_emitter.on(*args, **kwargs)
