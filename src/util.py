from functools import lru_cache
from logging import getLogger
from math import log10
from os import getenv
from typing import Any, Callable, Iterable, TypeVar

from pymanifold.lib import ManifoldClient

from . import Rule

ENVIRONMENT_VARIABLES = [
    "ManifoldAPIKey",     # REQUIRED. Allows trades, market creation, market resolution
    "GithubUsername",     # Optional. Allows you have a higher rate limit, make authorized requests
    "GithubAccessToken",  # Optional. See above
    "DBName",             # REQUIRED. The name of the database you wish to use
    "TelegramAPIKey",     # Optional. If you don't have a Telegram channel you wish to use, delete this line
                          # and run --console-only
    "TelegramChatID",     # Optional. See above
    "LogFile",            # REQUIRED. What file to put the log in
]
# If you don't need a specific environment variable, delete the line in this list
# That said, if you use a rule that requires some API and have no key for it, it will fail

T = TypeVar("T")


def fibonacci(start: int = 1) -> Iterable[int]:
    """Iterate over the fibonacci numbers."""
    x = 0
    y = 1
    for _ in range(start):
        x, y = y, x + y
    while True:
        yield x
        x, y = y, x + y


def pool_to_number(yes: float, no: float, p: float, start: float, end: float, isLogScale: bool = False) -> float:
    """Go from a pool of probability to a numeric answer."""
    pno = p * no
    probability = (pno / ((1 - p) * yes + pno))
    ret: float
    if isLogScale:
        logValue = log10(end - start + 1) * probability
        ret = max(start, min(end, 10**logValue + start - 1))
    else:
        ret = max(start, min(end, start + (end - start) * probability))
    return ret


def round_sig_figs(num: float, sig_figs: int = 4) -> str:
    """Round a number to the specified number of significant figures, then return it as a str."""
    return f"%.{sig_figs}g" % (num, )


def round_sig_figs_f(num: float, sig_figs: int = 4) -> float:
    """Round a number to the specified number of significant figures, then return it as a float."""
    return float(round_sig_figs(num, sig_figs))


def require_env(*env: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Enforce the presence of environment variables that may be necessary for a function to properly run."""
    def bar(func: Callable[..., T]) -> Callable[..., T]:
        def foo(*args: Any, **kwargs: Any) -> T:
            for x in env:
                if not getenv(x):
                    getLogger(__file__).error(f"Cannot run, as ${x} is not in the environment")
                    raise EnvironmentError("Please call 'source env.sh' first", x)
            return func(*args, **kwargs)

        return foo
    return bar


@lru_cache(maxsize=None)
@require_env("ManifoldAPIKey")
def get_client() -> ManifoldClient:
    """Return a (possibly non-unique) Manifold client."""
    return ManifoldClient(getenv("ManifoldAPIKey"))


def explain_abstract(time_rules: Iterable[Rule], value_rules: Iterable[Rule], **kwargs: Any) -> str:
    """Explain how the market will resolve and decide to resolve."""
    ret = "This market will resolve if any of the following are true:\n"
    for rule_ in time_rules:
        ret += rule_.explain_abstract(**kwargs)
    ret += ("\nIt will resolve based on the following decision tree:\n"
            "- If the human operator agrees:\n")
    for rule_ in value_rules:
        ret += rule_.explain_abstract(indent=1, **kwargs)
    ret += (
        "- Otherwise, a manually provided value\n\n"
        "Note that the bot operator reserves the right to resolve contrary to the purely automated rules to "
        "preserve the spirit of the market. All resolutions are first verified by the human operator."
        "\n\n"
        "The operator also reserves the right to trade on this market unless otherwise specified. Even if "
        "otherwise specified, the operator reserves the right to buy shares for subsidy or to trade for the "
        "purposes of cashing out liquidity.\n"
    )
    return ret
