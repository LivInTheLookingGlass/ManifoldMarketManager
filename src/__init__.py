"""Manifold Market Manager Library.

This module provides the ability to construct a Manifold Markets manager bot. In particular, it gives you a framework
to have automatically resolving markets. A future goal may be to allow trading, but this will likely be done using
limits, rather than time sensitive trades. Expect intervals of minutes, not microseconds.

In order to use this library, some things need to be loaded in your environment variables. See the comments below for
more information on this.
"""

from abc import ABC, abstractmethod
from importlib import import_module
from logging import Logger, getLogger
from os import getenv
from pathlib import Path
from pickle import dumps, loads
from sqlite3 import register_adapter, register_converter
from sys import modules
from sys import path as _sys_path
from traceback import format_exc
from typing import Any
from warnings import warn

_sys_path.append(str(Path(__file__).parent.joinpath("PyManifold")))

from pymanifold.types import DictDeserializable  # noqa: E402


class Rule(ABC, DictDeserializable):
    """The basic unit of market automation, rules defmine how a market should react to given events."""

    def __init__(self) -> None:
        self.logger: Logger = getLogger(f"{type(self).__qualname__}[{id(self)}]")

    @abstractmethod
    def value(
        self,
        market: 'Market'
    ) -> 'AnyResolution':
        """Return the formatted value of a rule, whether this is if one should resolve or a resolution value."""
        raise NotImplementedError(type(self))

    @abstractmethod
    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        """Explain how the market will resolve and decide to resolve."""
        raise NotImplementedError(type(self))

    def explain_specific(self, market: 'Market', indent: int = 0) -> str:
        """Explain why the market is resolving the way that it is."""
        warn("Using a default specific explanation. This probably isn't what you want!")
        return self.explain_abstract(indent=indent).rstrip('\n') + f" (-> {self.value(market)})\n"


from . import market, rule, util  # noqa: E402
from .market import Market  # noqa: E402
from .rule import DoResolveRule, ResolutionValueRule  # noqa: E402
from .util import (AnyResolution, BinaryResolution, FreeResponseResolution, MultipleChoiceResolution,  # noqa: E402
                   PseudoNumericResolution, get_client, require_env)

register_adapter(rule.Rule, dumps)  # type: ignore
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)
getLogger
__version_info__ = (0, 5, 0, 0, 1)
__all__ = [
    "__version_info__", "get_client", "market", "require_env", "rule", "util", "Market", "DoResolveRule",
    "ResolutionValueRule", "Rule", "AnyResolution", "BinaryResolution", "FreeResponseResolution",
    "MultipleChoiceResolution", "PseudoNumericResolution"
]

if getenv("DEBUG"):
    import sys

    def info(type, value, tb):  # type: ignore
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
exempt = ('__init__', '__main__', '__pycache__', 'application', 'test', 'PyManifold', *__all__)
for entry in Path(__file__).parent.iterdir():
    name = entry.name.rstrip(".py")
    if name.startswith('.') or name in exempt:
        continue
    try:
        setattr(modules[__name__], name, import_module("." + name, __name__))
        __all__.append(name)
    except ImportError:
        format_exc()
        warn(f"Unable to import extension module: {name}")
