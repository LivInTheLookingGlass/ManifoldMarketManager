"""Manifold Market Manager Library.

This module provides the ability to construct a Manifold Markets manager bot. In particular, it gives you a framework
to have automatically resolving markets. A future goal may be to allow trading, but this will likely be done using
limits, rather than time sensitive trades. Expect intervals of minutes, not microseconds.

In order to use this library, some things need to be loaded in your environment variables. See the comments below for
more information on this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
from os import getenv
from pathlib import Path
from pickle import dumps, loads
from sqlite3 import register_adapter, register_converter
from sys import path as _sys_path
from typing import TYPE_CHECKING, Generic, Iterable, Literal, Mapping, Sequence, Union, cast
from warnings import warn

from attrs import define, field

_sys_path.append(str(Path(__file__).parent.joinpath("PyManifold")))

from .caching import parallel  # noqa: E402
from .consts import AnyResolution, Outcome, T  # noqa: E402
from .util import DictDeserializable  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger
    from typing import Any

    from .consts import OutcomeType


@define(slots=False)  # type: ignore
class Rule(ABC, Generic[T], DictDeserializable):
    """The basic unit of market automation, rules defmine how a market should react to given events."""

    tags_used: set[str] = field(factory=set, init=False, repr=False, hash=False)
    logger: Logger = field(init=False, repr=False, hash=False)

    def __attrs_post_init__(self) -> None:
        """Ensure that the logger object is created."""
        if hasattr(super(), '__attrs_post_init__'):
            super().__attrs_post_init__()  # type: ignore
        self.logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    @abstractmethod
    def _value(
        self,
        market: Market
    ) -> T:  # pragma: no cover
        ...

    def __getstate__(self) -> Mapping[str, Any]:
        """Remove sensitive/non-serializable state before dumping to database."""
        state = self.__dict__.copy()
        if 'tags_used' in state:
            del state['tags_used']
        if 'logger' in state:
            del state['logger']
        return state

    def value(
        self,
        market: Market,
        format: Literal['NONE'] | OutcomeType = 'NONE',
        refresh: bool = False
    ) -> AnyResolution:
        """Return the resolution value of a market, appropriately formatted for its market type."""
        ret = self._value(market)
        if (ret is None) or (ret == "CANCEL") or (format == 'NONE'):
            return cast(AnyResolution, ret)
        elif format in Outcome.BINARY_LIKE():
            return self.__binary_value(market, ret)
        elif format in Outcome.MC_LIKE():
            return self.__multiple_choice_value(market, ret)
        raise ValueError()

    def __binary_value(self, market: Market, ret: Any) -> float:
        if not isinstance(ret, str) and isinstance(ret, Sequence):
            (ret, ) = ret
        elif isinstance(ret, Mapping) and len(ret) == 1:
            ret = cast(Union[str, int, float], next(iter(ret.items()))[0])

        if isinstance(ret, (int, float, )):
            return ret
        elif isinstance(ret, str):
            return float(ret)

        raise TypeError(ret, format, market)

    def __multiple_choice_value(self, market: Market, ret: Any) -> Mapping[int, float]:
        if isinstance(ret, Mapping):
            ret = {int(val): share for val, share in ret.items()}
        elif isinstance(ret, (int, str)):
            ret = {int(ret): 1}
        elif isinstance(ret, float) and ret.is_integer():
            ret = {int(ret): 1}
        elif isinstance(ret, Iterable):
            ret = {int(val): 1 for val in ret}
        else:
            raise TypeError(ret, format, market)
        return normalize_mapping(ret)

    @abstractmethod
    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:  # pragma: no cover
        raise NotImplementedError(type(self))

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        """Explain how the market will resolve and decide to resolve."""
        return self._explain_abstract(indent, **kwargs)

    def explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        """Explain why the market is resolving the way that it is."""
        return self._explain_specific(market, indent, sig_figs)

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        f_val = parallel(self._value, market)
        warn("Using a default specific explanation. This probably isn't what you want!")
        ret = self.explain_abstract(indent=indent).rstrip('\n')
        ret += " (-> "
        val = f_val.result()
        if val == "CANCEL":
            ret += "CANCEL)\n"
            return ret
        if isinstance(self, rule.DoResolveRule) or market.market.outcomeType == Outcome.BINARY:
            if val is True or val == 100:
                ret += "YES)\n"
            elif not val:
                ret += "NO)\n"
            else:
                ret += f"{round_sig_figs(cast(float, val))}%)\n"
        elif market.market.outcomeType == Outcome.PSEUDO_NUMERIC:
            ret += round_sig_figs(cast(float, val))
        elif market.market.outcomeType in Outcome.MC_LIKE():
            val_ = cast(Mapping[int, float], val)
            ret += "{"
            for idx, (key, weight) in enumerate(val_.items()):
                if idx:
                    ret += ", "
                ret += f"{key}: {round_sig_figs(weight * 100)}%"
            ret += "})\n"
        return ret


from . import market, rule, util  # noqa: E402
from .market import Market  # noqa: E402
from .rule import DoResolveRule, ResolutionValueRule  # noqa: E402
from .util import dynamic_import, get_client, normalize_mapping, require_env, round_sig_figs  # noqa: E402

register_adapter(rule.Rule, dumps)  # type: ignore
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)

VERSION = "0.7.0.1"
__version_info__ = tuple(int(x) for x in VERSION.split('.'))
__all__ = [
    "__version_info__", "VERSION", "DoResolveRule", "ResolutionValueRule", "Rule", "Market", "get_client", "rule",
    "util", "require_env"
]

if getenv("DEBUG"):  # pragma: no cover
    import sys

    def info(type, value, tb):  # type: ignore  # pragma: no cover
        """Open a postmortem pdb prompt on exception, if able."""
        if hasattr(sys, 'ps1') or not sys.stderr.isatty():
            # we are in interactive mode or we don't have a tty-like
            # device, so we call the default hook
            sys.__excepthook__(type, value, tb)
        else:
            import pdb
            import traceback

            # we are NOT in interactive mode, print the exception...
            traceback.print_exception(type, value, tb)
            print()
            # ...then start the debugger in post-mortem mode.
            pdb.post_mortem(tb)

    sys.excepthook = info

# dynamically load optional plugins where able to
exempt = {'__init__', '__main__', '__pycache__', 'application', 'test', 'PyManifold', 'py.typed', *__all__}
dynamic_import(__file__, __name__, __all__, exempt)
