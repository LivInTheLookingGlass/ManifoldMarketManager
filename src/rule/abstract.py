from __future__ import annotations

from dataclasses import dataclass, field
from os import urandom
from random import Random
from typing import TYPE_CHECKING, cast

from .. import Rule, T
from . import ResolutionValueRule, get_rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Mapping, Sequence

    from ..market import Market


@dataclass  # type: ignore
class UnaryRule(Rule[T]):
    """Perform a unary operation on another DoResolveRule."""

    child: Rule[T]

    @classmethod
    def from_dict(cls, env: Mapping[str, Any]) -> 'UnaryRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        type_, kwargs = env["child"]
        env_copy["child"] = get_rule(type_).from_dict(kwargs)
        return cast(UnaryRule[T], super().from_dict(env_copy))


@dataclass  # type: ignore
class BinaryRule(Rule[T]):
    """Perform a binary operation on two Rules."""

    rule1: Rule[T]
    rule2: Rule[T]

    @classmethod
    def from_dict(cls, env: Mapping[str, Any]) -> 'BinaryRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        for name in ('rule1', 'rule2'):
            type_, kwargs = env[name]
            env_copy[name] = get_rule(type_).from_dict(kwargs)
        return cast(BinaryRule[T], super().from_dict(env_copy))


@dataclass  # type: ignore
class VariadicRule(Rule[T]):
    """Perform a variadic operation on many Rules."""

    rules: list[Rule[T]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, env: Mapping[str, Any]) -> 'VariadicRule[T]':
        """Take a dictionary and return an instance of the associated class."""
        env_copy = dict(env)
        arr = env["rules"]
        for idx, (type_, kwargs) in enumerate(arr):
            env_copy["rules"][idx] = get_rule(type_).from_dict(kwargs)
        return cast(VariadicRule[T], super().from_dict(env_copy))


@dataclass  # type: ignore
class ResolveRandomSeed(ResolutionValueRule):
    """Abstract class that handles the nitty-gritty of the Random object."""

    seed: int | float | str | bytes | bytearray = urandom(16)
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def _value(self, market: Market) -> Any:
        source = Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret
