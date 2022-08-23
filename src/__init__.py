"""Manifold Market Manager Library.

This module provides the ability to construct a Manifold Markets manager bot. In particular, it gives you a framework
to have automatically resolving markets. A future goal may be to allow trading, but this will likely be done using
limits, rather than time sensitive trades. Expect intervals of minutes, not microseconds.

In order to use this library, some things need to be loaded in your environment variables. See the comments below for
more information on this.
"""

from logging import getLogger
from os import getenv
from pathlib import Path
from pickle import dumps, loads
from sqlite3 import register_adapter, register_converter
from sys import path as _sys_path
from typing import Dict, Optional, Union

_sys_path.append(str(Path(__file__).parent.joinpath("PyManifold")))

from pymanifold.types import DictDeserializable  # noqa: E402

ENVIRONMENT_VARIABLES = [
    "ManifoldAPIKey",   # REQUIRED. Allows trades, market creation, market resolution
    "GithubAPIKey",     # Optional. Allows you to query Pull Requests
    "DBName",           # REQUIRED. The name of the database you wish to use
    "TelegramAPIKey",   # Optional. If you don't have a Telegram channel you wish to use, delete this line
                        # and run --console-only
    "TelegramChatID",   # Optional. See above
    "LogFile",          # REQUIRED. What file to put the log in
]
# If you don't need a specific environment variable, delete the line in this list
# That said, if you use a rule that requires some API and have no key for it, it will fail


def require_env(*env: str):
    """Enforce the presence of environment variables that may be necessary for a function to properly run."""
    def bar(func):
        def foo(*args, **kwargs):
            for x in env:
                if not getenv(x):
                    getLogger(__file__).error(f"Cannot run, as ${x} is not in the environment")
                    raise EnvironmentError("Please call 'source env.sh' first", x)
            return func(*args, **kwargs)

        return foo
    return bar


class Rule(DictDeserializable):
    """The basic unit of market automation, rules defmine how a market should react to given events."""

    def value(self, market: 'Market', format='') -> Optional[Union[int, float, str, Dict[int, float]]]:
        """Return the formatted value of a rule, whether this is if one should resolve or a resolution value."""
        raise NotImplementedError()


from . import market  # noqa: E402
from . import rule  # noqa: E402
from .market import Market  # noqa: E402
from .rule import DoResolveRule, ResolutionValueRule  # noqa: E402

register_adapter(rule.Rule, dumps)
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)

__version_info__ = (0, 3, 0, 0, 0)
__all__ = (
    "__version_info__", "market", "require_env", "rule", "Market", "DoResolveRule", "ResolutionValueRule", "Rule"
)

if getenv("DEBUG"):
    import sys

    def info(type, value, tb):
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
