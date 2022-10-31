"""Contains utility functions."""

from __future__ import annotations

from functools import lru_cache
from hashlib import blake2b
from importlib import import_module
from itertools import count
from logging import getLogger, warn
from math import ceil
from os import getenv
from pathlib import Path
from sys import modules
from traceback import print_exc
from typing import TYPE_CHECKING

from pymanifold.lib import ManifoldClient
from pymanifold.types import Market as APIMarket
from pymanifold.utils.math import number_to_prob_cpmm1  # noqa: F401

from .consts import EnvironmentVariable, Outcome

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable, Collection, Iterable, Mapping, MutableSequence, Sequence, Type, TypeVar, Union

    from . import Market, Rule

    ModJSONType = Union[int, float, bool, str, None, Rule[Any], Sequence['ModJSONType'], Mapping[str, 'ModJSONType']]
    ModJSONDict = Mapping[str, ModJSONType]
    T = TypeVar("T")


class DictDeserializable:
    """A port of PyManifold's DictDeserializable that does not check against the signature."""

    @classmethod
    def from_dict(cls: Type[T], env: ModJSONDict) -> T:
        """Take a dictionary and return an instance of the associated class."""
        return cls(**env)


def hash_to_randrange(buff: bytes, *args: int, **kwargs: int) -> int:
    """Generate a 'random' number by hashing a buffer."""
    active_range = range(*args, **kwargs)
    size = len(active_range)
    mask = 2**size - 1
    byte_length = ceil((size - 1).bit_length() / 8)
    ret: int
    for idx in count():
        hashobj = blake2b(buff, digest_size=byte_length, salt=str(idx).encode())
        as_int = int.from_bytes(hashobj.digest(), 'little') & mask
        if as_int < size:
            ret = active_range[as_int]
            break
    return ret


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
    market: Market | APIMarket, exclude: Collection[int] = (), *filters: Callable[[int, float], bool]
) -> dict[int, float]:
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
    mkt: APIMarket = market  # type: ignore[assignment]
    if not isinstance(market, APIMarket):
        mkt = market.market
    if mkt.outcomeType not in Outcome.MC_LIKE():
        raise RuntimeError("Cannot extract a mapping from binary markets")
    assert mkt.answers
    initial: dict[int, float] = {}
    answer: dict[str, str | float]
    for answer in mkt.answers:
        key = int(answer['id'])
        initial[key] = float(answer['probability'])
    return {
        key: value for key, value in initial.items()
        if key not in exclude and not any(f(key, value) for f in filters)
    }


def normalize_mapping(answers: Mapping[T, float]) -> dict[T, float]:
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
            if not all(getenv(x) for x in env):
                getLogger(__file__).error(f"Cannot run, as one of ${env} is not in the environment")
                raise EnvironmentError("Please call 'source env.sh' first", env)
            return func(*args, **kwargs)

        return foo
    return bar


@lru_cache(maxsize=None)
@require_env(EnvironmentVariable.ManifoldAPIKey)
def get_client() -> ManifoldClient:
    """Return a (possibly non-unique) Manifold client."""
    return ManifoldClient(getenv("ManifoldAPIKey"))


def explain_abstract(time_rules: Iterable[Rule[Any]], value_rules: Iterable[Rule[Any]], **kwargs: Any) -> str:
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
    for entry in Path(fname).parent.glob("[!.]*"):
        name = entry.name.rstrip(".py")
        if name in exempt:
            continue
        try:
            setattr(modules[mname], name, import_module("." + name, mname))
            __all__.append(name)
        except ImportError:  # pragma: no cover
            print_exc()
            warn(f"Unable to import extension module: {mname}.{name}")
