from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from random import Random
from typing import Any, DefaultDict, Dict, MutableSequence, Optional, Sequence, Tuple, Union, cast

from . import get_rule, DoResolveRule, ResolutionValueRule
from ..market import Market


@dataclass
class NegateRule(DoResolveRule):
    """Negate another DoResolveRule."""

    child: DoResolveRule

    def value(self, market: Market) -> bool:
        return not self.child.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return (
            f"{'  ' * indent}- If the rule below resolves False\n" +
            self.child.explain_abstract(indent + 1, **kwargs)
        )

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        if "child" in env:
            try:
                type_, kwargs = env["child"]
                env["child"] = get_rule(type_).from_dict(kwargs)
            except Exception:
                pass
        return super().from_dict(env)


@dataclass
class EitherRule(DoResolveRule):
    """Return the OR of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) or self.rule2.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = get_rule(type_).from_dict(kwargs)
                except Exception:
                    pass
        return super().from_dict(env)


@dataclass
class BothRule(DoResolveRule):
    """Return the AND of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) and self.rule2.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = get_rule(type_).from_dict(kwargs)
                except Exception:
                    pass
        return super().from_dict(env)


@dataclass
class ResolveAtTime(DoResolveRule):
    """Return True if the specified time is in the past."""

    resolve_at: datetime

    def value(self, market) -> bool:
        try:
            return datetime.utcnow() >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the current time is past {self.resolve_at}\n"


@dataclass
class ResolveToValue(ResolutionValueRule):
    resolve_value: Any

    def _value(self, market):
        return self.resolve_value

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the specific value {self.resolve_value}\n"


@dataclass  # type: ignore
class ResolveRandomSeed(ResolutionValueRule):
    seed: Any
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def _value(self, market) -> float:
        source = Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret


@dataclass
class ResolveRandomIndex(ResolveRandomSeed):
    size: Optional[int] = None
    start: int = 0

    def __init__(self, seed, *args, size=None, start=0, **kwargs):
        self.start = start
        self.size = size
        if size is None:
            method = 'choices'
        else:
            method = 'randrange'
        super().__init__(seed, method, *args, **kwargs)

    def _value(self, market) -> int:
        if self.method == 'randrange':
            self.args = (self.start, self.size)
        else:
            items = [(int(idx), float(obj)) for idx, obj in market.market.pool.items() if int(idx) >= self.start]
            self.args = (range(self.start, self.start + len(items)), )
            self.kwargs["weights"] = [prob for _, prob in items]
        return cast(int, super()._value(market))

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolve to a random index, given some original seed. This one operates on a "
        if self.method == 'randrange':
            ret += f"fixed range of integers in ({self.start} <= x < {self.size}).\n"
        else:
            ret += f"dynamic range based on the current pool and probabilities, but starting at {self.start}.\n"
        return ret


@dataclass
class ResolveMultipleValues(ResolutionValueRule):
    shares: MutableSequence[Tuple[ResolutionValueRule, float]] = field(default_factory=list)

    def _value(self, market: Market) -> Dict[Union[str, int, float], float]:
        ret: DefaultDict[int, float] = defaultdict(float)
        for rule, part in self.shares:
            val = cast(Dict[Union[str, int], float], rule.value(market, format='FREE_RESPONSE'))
            for idx, value in val.items():
                ret[int(idx)] += value * part
        return {key: value for key, value in ret.items()}

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}Resolves to the weighted union of multiple other values.\n"
        indent += 1
        for rule, weight in self.shares:
            ret += f"{'  ' * indent} - At a weight of {weight}\n"
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        shares: MutableSequence[ResolutionValueRule, float] = env['shares']
        new_shares = []
        for rule, weight in shares:
            try:
                type_, kwargs = rule
                new_rule = get_rule(type_).from_dict(kwargs)
                new_shares.append((new_rule, weight))
            except Exception:
                pass
        env['shares'] = new_shares
        return super().from_dict(env)