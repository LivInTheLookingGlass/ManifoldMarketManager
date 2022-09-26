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
from typing import TYPE_CHECKING, Generic, Literal, Mapping, Optional, Sequence, TypeVar, Union, cast
from warnings import warn

_sys_path.append(str(Path(__file__).parent.joinpath("PyManifold")))

from pymanifold.types import DictDeserializable  # noqa: E402

BinaryResolution = Union[Literal["CANCEL"], bool, float]
PseudoNumericResolution = Union[Literal["CANCEL"], float]
FreeResponseResolution = Union[Literal["CANCEL"], Mapping[str, float], Mapping[int, float], Mapping[float, float]]
MultipleChoiceResolution = FreeResponseResolution
AnyResolution = Union[BinaryResolution, PseudoNumericResolution, FreeResponseResolution, MultipleChoiceResolution]
T = TypeVar("T", bound=Optional[AnyResolution])

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger
    from typing import Any


class Rule(ABC, Generic[T], DictDeserializable):
    """The basic unit of market automation, rules defmine how a market should react to given events."""

    def __init__(self) -> None:
        self.logger: Logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    @abstractmethod
    def _value(
        self,
        market: Market
    ) -> AnyResolution:  # pragma: no cover
        ...

    def value(
        self,
        market: Market,
        format: Optional[Literal['NONE', 'BINARY', 'PSEUDO_NUMERIC', 'FREE_RESPONSE', 'MULTIPLE_CHOICE']] = None
    ) -> AnyResolution:
        """Return the resolution value of a market, appropriately formatted for its market type."""
        if format is None:
            format = market.market.outcomeType
        ret: Union[str, AnyResolution] = self._value(market)
        if (ret is None) or (ret == "CANCEL") or (format == 'NONE'):
            return cast(AnyResolution, ret)
        elif format in ('BINARY', 'PSEUDO_NUMERIC'):
            return self._binary_value(market, ret)
        elif format in ('FREE_RESPONSE', 'MULTIPLE_CHOICE'):
            return self._multiple_choice_value(market, ret)
        raise ValueError()

    def _binary_value(self, market: Market, ret: Any) -> float:
        if not isinstance(ret, str) and isinstance(ret, Sequence) and len(ret) == 1:
            ret = ret[0]
        elif isinstance(ret, Mapping) and len(ret) == 1:
            ret = cast(Union[str, int, float], next(iter(ret.items()))[0])

        if isinstance(ret, (int, float, )):
            return ret
        elif isinstance(ret, str):
            ret = float(ret)
            if ret.is_integer():
                return int(ret)
            return cast(float, ret)

        raise TypeError(ret, format, market)

    def _multiple_choice_value(self, market: Market, ret: Any) -> Mapping[int, float]:
        if isinstance(ret, Mapping):
            return {int(val): share for val, share in ret.items()}
        elif isinstance(ret, Sequence) and len(ret) == 1:
            ret = ret[0]

        if isinstance(ret, str):
            return {int(ret): 1}
        elif isinstance(ret, int):
            return {ret: 1}
        elif isinstance(ret, float):
            if ret.is_integer():
                return {int(ret): 1}
            raise ValueError()

        raise TypeError(ret, format, market)

    @abstractmethod
    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        raise NotImplementedError(type(self))

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        """Explain how the market will resolve and decide to resolve."""
        return self._explain_abstract(indent, **kwargs)

    def explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        """Explain why the market is resolving the way that it is."""
        return self._explain_specific(market, indent, sig_figs)

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        warn("Using a default specific explanation. This probably isn't what you want!")
        ret = self.explain_abstract(indent=indent).rstrip('\n')
        ret += " (-> "
        val = self._value(market)
        if val == "CANCEL":
            ret += "CANCEL)\n"
            return ret
        if isinstance(self, rule.DoResolveRule) or market.market.outcomeType == "BINARY":
            if val is True or val == 100:
                ret += "YES)\n"
            elif not val:
                ret += "NO)\n"
            else:
                ret += round_sig_figs(cast(float, val) * 100)
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            ret += round_sig_figs(cast(float, val))
        elif market.market.outcomeType in ("FREE_RESPONSE", "MULTIPLE_CHOICE"):
            assert not isinstance(val, (float, str))
            ret += "{"
            for idx, (key, weight) in enumerate(val.items()):
                if idx:
                    ret += ", "
                ret += f"{key}: {round_sig_figs(weight * 100)}%"
            ret += "})\n"
        return ret


from . import market, rule, util  # noqa: E402
from .market import Market  # noqa: E402
from .rule import DoResolveRule, ResolutionValueRule  # noqa: E402
from .util import dynamic_import, get_client, require_env, round_sig_figs  # noqa: E402

register_adapter(rule.Rule, dumps)  # type: ignore
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)

VERSION = "0.6.0.7"
__version_info__ = tuple(int(x) for x in VERSION.split('.'))
__all__ = [
    "__version_info__", "VERSION", "AnyResolution", "BinaryResolution", "DoResolveRule", "FreeResponseResolution",
    "MultipleChoiceResolution", "PseudoNumericResolution", "ResolutionValueRule", "Rule", "Market", "get_client",
    "require_env", "rule", "util"
]

if getenv("DEBUG"):
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
