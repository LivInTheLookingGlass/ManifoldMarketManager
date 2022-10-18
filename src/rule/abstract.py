"""Contains abstract subclasses of Rule which allow for forms of pluggable behavior."""

from __future__ import annotations

from os import urandom
from random import Random
from typing import TYPE_CHECKING, Generic, cast

from attrs import Factory, define

from .. import Rule
from ..consts import T
from ..util import round_sig_figs
from . import ResolutionValueRule, get_rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, ClassVar, Sequence

    from pymanifold.types import JSONDict

    from ..market import Market
    from ..util import ModJSONDict

SENTINEL_STUB = "A programatic explanation was not provided"


@define(slots=False)  # type: ignore
class AbstractRule(Generic[T], Rule[T]):
    """Provide a rule where the explanations are pre-generated."""

    _explainer_stub: ClassVar[str] = SENTINEL_STUB

    def __init_subclass__(cls) -> None:
        """Enforce that subclasses provide an explanatory stub."""
        if cls._explainer_stub is SENTINEL_STUB and cls._value != AbstractRule._value:
            raise ValueError("You need to override _explainer_stub to subclass this")
        return super().__init_subclass__()

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- {self._explainer_stub}\n"

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        return f"{'  ' * indent}- {self._explainer_stub} (-> {self.value(market, format='NONE')})\n"


@define(slots=False)  # type: ignore
class UnaryRule(AbstractRule[T]):
    """Perform a unary operation on another DoResolveRule."""

    child: Rule[T]

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return super()._explain_abstract(indent, **kwargs) + self.child.explain_abstract(indent + 1, **kwargs)

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        return super()._explain_specific(market, indent, sig_figs) +\
            self.child.explain_specific(market, indent + 1, sig_figs)

    @classmethod
    def from_dict(cls, env: ModJSONDict) -> 'UnaryRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        child: tuple[str, ModJSONDict] = env["child"]  # type: ignore[assignment]
        type_, kwargs = child
        env_copy["child"] = get_rule(type_).from_dict(kwargs)
        return super().from_dict(env_copy)


@define(slots=False)  # type: ignore
class BinaryRule(AbstractRule[T]):
    """Perform a binary operation on two Rules."""

    rule1: Rule[T]
    rule2: Rule[T]

    @classmethod
    def from_dict(cls, env: ModJSONDict) -> 'BinaryRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        for name in ('rule1', 'rule2'):
            child: tuple[str, ModJSONDict] = env[name]  # type: ignore[assignment]
            type_, kwargs = child
            env_copy[name] = get_rule(type_).from_dict(kwargs)
        return super().from_dict(env_copy)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = super()._explain_abstract(indent, **kwargs)
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = super()._explain_specific(market, indent, sig_figs)
        ret += self.rule1.explain_specific(market, indent + 1, sig_figs)
        ret += self.rule2.explain_specific(market, indent + 1, sig_figs)
        return ret


@define(slots=False)  # type: ignore
class VariadicRule(AbstractRule[T]):
    """Perform a variadic operation on many Rules."""

    rules: list[Rule[T]] = Factory(list)

    @classmethod
    def from_dict(cls, env: ModJSONDict) -> 'VariadicRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        arr: Sequence[tuple[str, ModJSONDict]] = env.get("rules", [])  # type: ignore[assignment]
        rules: list[None | Rule[Any]] = [None] * len(arr)
        for idx, (type_, kwargs) in enumerate(arr):
            rules[idx] = get_rule(type_).from_dict(kwargs)
        env_copy["rules"] = rules
        return super().from_dict(env_copy)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = super()._explain_abstract(indent, **kwargs)
        for rule in self.rules:
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        val = round_sig_figs(cast(float, self._value(market)), sig_figs)
        ret = f"{'  ' * indent}- {self._explainer_stub} (-> {val})\n"
        for rule in self.rules:
            ret += rule.explain_specific(market, indent + 1, sig_figs)
        return ret


@define(slots=False)  # type: ignore
class ResolveRandomSeed(ResolutionValueRule):
    """Abstract class that handles the nitty-gritty of the Random object."""

    seed: int | float | str | bytes | bytearray = urandom(16)
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: JSONDict = Factory(dict)

    def _value(self, market: Market) -> Any:
        source = Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret
