from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, Dict, Union, cast

from ...util import normalize_mapping
from .. import ResolutionValueRule, get_rule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, DefaultDict, Mapping, MutableSequence, Optional, Sequence, Tuple

    from ... import AnyResolution, FreeResponseResolution, MultipleChoiceResolution
    from ...market import Market


@dataclass
class ResolveToValue(ResolutionValueRule):
    """Resolve to a pre-specified value."""

    resolve_value: AnyResolution

    def _value(self, market: Market) -> AnyResolution:
        return self.resolve_value

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the specific value {self.resolve_value}\n"


@dataclass  # type: ignore
class ResolveRandomSeed(ResolutionValueRule):
    """Abstract class that handles the nitty-gritty of the Random object."""

    seed: Any
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def _value(self, market: Market) -> Any:
        source = Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret


@dataclass
class ResolveRandomIndex(ResolveRandomSeed):
    """Resolve to a random index in a market."""

    size: Optional[int] = None
    start: int = 0

    def __init__(
        self,
        seed: Optional[Union[int, float, str, bytes, bytearray]],
        *args: Any,
        size: Optional[int] = None,
        start: int = 0,
        **kwargs: Any
    ) -> None:
        self.start = start
        self.size = size
        if size is None:
            method = 'choices'
        else:
            method = 'randrange'
        super().__init__(seed, method, *args, **kwargs)

    def _value(self, market: Market) -> int:
        if self.method == 'randrange':
            self.args = (self.start, self.size)
        else:
            items = [(int(idx), float(obj)) for idx, obj in market.market.pool.items() if int(idx) >= self.start]
            self.args = (range(self.start, self.start + len(items)), )
            self.kwargs["weights"] = [prob for _, prob in items]
        return cast(int, super()._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolve to a random index, given some original seed. This one operates on a "
        if self.method == 'randrange':
            ret += f"fixed range of integers in ({self.start} <= x < {self.size}).\n"
        else:
            ret += f"dynamic range based on the current pool and probabilities, but starting at {self.start}.\n"
        return ret


@dataclass
class ResolveMultipleValues(ResolutionValueRule):
    """Resolve to multiple values with different shares."""

    shares: MutableSequence[Tuple[ResolutionValueRule, float]] = field(default_factory=list)

    def _value(self, market: Market) -> Union[FreeResponseResolution, MultipleChoiceResolution]:
        ret: DefaultDict[int, float] = defaultdict(float)
        for rule, part in self.shares:
            val = cast(Dict[Union[str, int], float], rule.value(market, format='FREE_RESPONSE'))
            for idx, value in val.items():
                ret[int(idx)] += value * part
        return normalize_mapping(ret)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}Resolves to the weighted union of multiple other values.\n"
        indent += 1
        for rule, weight in self.shares:
            ret += f"{'  ' * indent} - At a weight of {weight}\n"
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env: Mapping[str, Any]) -> 'ResolveMultipleValues':
        """Take a dictionary and return an instance of the associated class."""
        env_copy: Dict[str, Any] = dict(env)
        shares: MutableSequence[Tuple[ResolutionValueRule, float]] = env['shares']
        new_shares = []
        for rule, weight in shares:
            try:
                type_, kwargs = rule
                new_rule = get_rule(type_).from_dict(kwargs)
                new_shares.append((new_rule, weight))
            except Exception:
                pass
        env_copy['shares'] = new_shares
        return cast(ResolveMultipleValues, super().from_dict(env_copy))
