from functools import lru_cache
from importlib import import_module
from logging import getLogger, warn
from math import log10
from os import getenv
from pathlib import Path
from sys import modules
from traceback import print_exc
from typing import (TYPE_CHECKING, Any, Callable, Collection, Dict, Iterable, Mapping, MutableSequence, TypeVar, Union,
                    cast)

from pymanifold.lib import ManifoldClient
from pymanifold.types import Market as APIMarket

if TYPE_CHECKING:
    from . import Market, Rule

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


def market_to_answer_map(
    market: Union['Market', 'APIMarket'], exclude: Collection[int] = (), *filters: Callable[[int, float], bool]
) -> Dict[int, float]:
    """Given a market, grab its current list of answers and put it in a standardized format, applying given filters.

    Parameters
    ----------
    market : Market | PyManifold.lib.Market
        The market wrapper for which we want the current answer pool.
    exclude : Collection[int], optional
        Some collection of ids to exclude. Preferrably a set() or range(). by default ()
    filters : *Callable[[int, float], bool]
        A collection of functions which will be fed the answer ID and probability. If any return True, that answer
        is excluded. By default ()

    Returns
    -------
    Mapping[int, float]
        A mapping of integer ids to probabilities in [0...1]. Note that Manifold expects ids as strings, but they are
        returned as integers for ease of processing. Note also that this mapping is NOT normalized.

    Raises
    ------
    RuntimeError
        If a non-supported market is fed
    """
    if isinstance(market, APIMarket):
        mkt: APIMarket = market
    else:
        mkt = market.market
    if mkt.outcomeType == "FREE_RESPONSE":
        initial = {
            int(answer['id']): float(answer['probability'])
            for answer in mkt.answers
        }
    elif mkt.outcomeType == "MULTIPLE_CHOICE":
        # TODO: reimplement dpm-2 math so this is actually by probability
        pool = cast(Mapping[Any, float], mkt.pool)
        total = sum(answer**2 for answer in pool.values()) + 100**2
        initial = {
            int(answer): weight**2 / total
            for answer, weight in pool.items()
        }
    else:
        raise RuntimeError("Cannot extract a mapping from binary markets")
    return {
        key: value for key, value in initial.items()
        if key not in exclude and not any(f(key, value) for f in filters)
    }


def normalize_mapping(answers: Mapping[T, float]) -> Dict[T, float]:
    """Take a mapping of answers and normalize it such that the sum of their weights is 1."""
    total = sum(answers.values())
    return {key: value / total for key, value in answers.items()}


def pool_to_prob_cpmm1(yes: float, no: float, p: float) -> float:
    """Go from a pool of YES/NO to a probability using Maniswap."""
    if yes <= 0 or no <= 0 or not (0 < p < 1):
        raise ValueError()
    pno = p * no
    return pno / ((1 - p) * yes + pno)


def pool_to_number_cpmm1(yes: float, no: float, p: float, start: float, end: float, isLogScale: bool = False) -> float:
    """Go from a pool of probability to a numeric answer."""
    if start >= end:
        raise ValueError()
    probability = pool_to_prob_cpmm1(yes, no, p)
    return prob_to_number_cpmm1(probability, start, end, isLogScale)


def prob_to_number_cpmm1(probability: float, start: float, end: float, isLogScale: bool = False) -> float:
    """Go from a probability to a numeric answer."""
    if isLogScale:
        ret: float = (end - start + 1)**probability + start - 1
    else:
        ret = start + (end - start) * probability
    ret = max(start, min(end, ret))
    return ret


def number_to_prob_cpmm1(current: float, start: float, end: float, isLogScale: bool = False) -> float:
    """Go from a numeric answer to a probability."""
    if not (start <= current <= end):
        raise ValueError()
    if isLogScale:
        return log10(current - start + 1) / log10(end - start + 1)
    return (current - start) / (end - start)


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


def explain_abstract(time_rules: Iterable['Rule[Any]'], value_rules: Iterable['Rule[Any]'], **kwargs: Any) -> str:
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


def dynamic_import(fname: str, mname: str, __all__: MutableSequence[str], exempt: Collection[str]) -> None:
    """Dynamically import submodules and add them to the export list."""
    for entry in Path(fname).parent.iterdir():
        name = entry.name.rstrip(".py")
        if name.startswith('.') or name in exempt:
            continue
        try:
            setattr(modules[mname], name, import_module("." + name, mname))
            __all__.append(name)
        except ImportError:
            print_exc()
            warn(f"Unable to import extension module: {mname}.{name}")
