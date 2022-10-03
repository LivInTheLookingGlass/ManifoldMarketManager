from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Union, cast

from .. import BinaryResolution, PseudoNumericResolution
from ..util import normalize_mapping, round_sig_figs
from . import DoResolveRule, ResolutionValueRule, get_rule
from .abstract import BinaryRule, ResolveRandomSeed, UnaryRule, VariadicRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, DefaultDict, Literal, Mapping, MutableSequence, Optional

    from .. import AnyResolution, FreeResponseResolution, MultipleChoiceResolution
    from ..market import Market


class NegateRule(UnaryRule[BinaryResolution]):
    """Negate another DoResolveRule."""

    def _value(self, market: Market) -> bool:
        return not self.child._value(market)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolve False if the below is True, and vice versa\n" +\
               self.child.explain_abstract(indent + 1, **kwargs)

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        return f"{'  ' * indent}-  (-> {self.value(market)})\n" +\
               self.child.explain_specific(market, indent + 1)


class EitherRule(BinaryRule[BinaryResolution]):
    """Return the OR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) or bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- \n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve True if either of the below resolves True, otherwise resolve False (-> "
               f"{self.value(market, format='NONE')})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class BothRule(BinaryRule[BinaryResolution]):
    """Return the AND of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) and bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- \n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve True if both of the below resolve to True, otherwise resolve False (-> "
               f"{self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class NANDRule(BinaryRule[BinaryResolution]):
    """Return the NAND of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) and self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- \n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve True if one or more of the below resolves False, otherwise resolve False "
               f"(-> {self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class NeitherRule(BinaryRule[BinaryResolution]):
    """Return the NOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) or self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolve False if either of the below resolve to True, otherwise resolve True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve False if either of the below resolve to True, otherwise resolve True (-> "
               f"{self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class XORRule(BinaryRule[BinaryResolution]):
    """Return the XOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(bool(self.rule1._value(market)) ^ bool(self.rule2._value(market)))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolve False if the below resolve to the same value, otherwise resolve True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve False if the below resolve to the same value, otherwise resolve True (-> "
               f"{self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class XNORRule(BinaryRule[BinaryResolution]):
    """Return the XNOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) == bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolve True if the below resolve to the same value, otherwise resolve False\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve True if the below resolve to the same value, otherwise resolve False (-> "
               f"{self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class ImpliesRule(BinaryRule[BinaryResolution]):
    """Return the implication of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not self.rule1._value(market) or bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- \n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolve True if the next line resolves False, otherwise resolves to the value of "
               f"the item after (-> {self.value(market)})\n")
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


@dataclass
class ResolveAtTime(DoResolveRule):
    """Return True if the specified time is in the past."""

    resolve_at: datetime

    def _value(self, market: Market) -> bool:
        """Return True iff the current time is after resolve_at."""
        try:
            return datetime.now(timezone.utc) >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolve True if the current time is past {self.resolve_at}, otherwise resolve False\n"


@dataclass
class ResolveToValue(ResolutionValueRule):
    """Resolve to a pre-specified value."""

    resolve_value: AnyResolution

    def _value(self, market: Market) -> AnyResolution:
        return self.resolve_value

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the specific value {self.resolve_value}\n"


class ModulusRule(BinaryRule[PseudoNumericResolution]):
    """Return the modulus of two other DoResolveRules."""

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        val1, val2 = self.rule1._value(market), self.rule2._value(market)
        if val1 == "CANCEL" or val2 == "CANCEL":
            return "CANCEL"
        return val1 % val2

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- A mod B, where A is the next line and B the line after\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        val: str | float = self._value(market)
        if val != "CANCEL":
            val = round_sig_figs(cast(float, val), sig_figs)
        ret = f"{'  ' * indent}- A mod B, where A is the next line and B the line after (-> {val})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class AdditiveRule(VariadicRule[PseudoNumericResolution]):
    """Return the sum of many other Rules."""

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        """Return the sum of the underlying rules."""
        ret: float = 0
        for rule in self.rules:
            val = cast(
                PseudoNumericResolution,
                rule.value(market, format='PSEUDO_NUMERIC')
            )
            if val == "CANCEL":
                return "CANCEL"
            ret += val
        return ret

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- The sum of the below\n"
        for rule in self.rules:
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        val = round_sig_figs(cast(float, self._value(market)), sig_figs)
        ret = f"{'  ' * indent}- The sum of the below (-> {val})\n"
        for rule in self.rules:
            ret += rule.explain_specific(market, indent + 1, sig_figs)
        return ret


class MultiplicitiveRule(VariadicRule[PseudoNumericResolution]):
    """Return the product of many other Rules."""

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        """Return the product of the underlying rules."""
        ret: float = 0
        for rule in self.rules:
            val = cast(
                PseudoNumericResolution,
                rule.value(market, format='PSEUDO_NUMERIC')
            )
            if val == "CANCEL":
                return "CANCEL"
            ret *= val
        return ret

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- The product of the below\n"
        for rule in self.rules:
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        val = round_sig_figs(cast(float, self._value(market)), sig_figs)
        ret = f"{'  ' * indent}- The product of the below (-> {val})\n"
        for rule in self.rules:
            ret += rule.explain_specific(market, indent + 1, sig_figs)
        return ret


@dataclass
class ResolveRandomIndex(ResolveRandomSeed):
    """Resolve to a random index in a market."""

    size: Optional[int] = None
    start: int = 0

    def __init__(
        self,
        seed: int | float | str | bytes | bytearray,
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

    shares: MutableSequence[tuple[ResolutionValueRule, float]] = field(default_factory=list)

    def _value(self, market: Market) -> FreeResponseResolution | MultipleChoiceResolution:
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
        env_copy: dict[str, Any] = dict(env)
        shares: MutableSequence[tuple[ResolutionValueRule, float]] = env['shares']
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
