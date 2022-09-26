from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from ... import Rule, T
from .. import get_rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Mapping

__all__ = ('BinaryRule', 'UnaryRule', 'VariadicRule', 'time', 'value')


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


from . import time, value  # noqa: E402
