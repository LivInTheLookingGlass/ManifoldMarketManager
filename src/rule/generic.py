"""Contains generic rules, which don't interact markets other than their assigned one, & don't cause any mutations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Generic, Mapping, Optional, Tuple, Union, cast

from attrs import Factory, define

from .. import Rule
from ..caching import parallel
from ..consts import BinaryResolution, PseudoNumericResolution, T
from ..util import normalize_mapping
from . import DoResolveRule, ResolutionValueRule, get_rule
from .abstract import BinaryRule, ResolveRandomSeed, UnaryRule, VariadicRule

if TYPE_CHECKING:  # pragma: no cover
    from concurrent.futures import Future
    from typing import Any, ClassVar, DefaultDict, Literal, MutableSequence

    from ..consts import FreeResponseResolution, MultipleChoiceResolution
    from ..market import Market
    from ..util import ModJSONDict


@define(slots=False)
class NegateRule(UnaryRule[Optional[BinaryResolution]]):
    """Negate another DoResolveRule."""

    _explainer_stub: ClassVar[str] = "Resolve False if the below is True, and vice versa"

    def _value(self, market: Market) -> bool:
        return not self.child._value(market)


@define(slots=False)
class EitherRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the OR of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve True if either of the below resolves True, otherwise resolve False"

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) or bool(self.rule2._value(market))


@define(slots=False)
class BothRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the AND of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve True if both of the below resolve to True, otherwise resolve False"

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) and bool(self.rule2._value(market))


@define(slots=False)
class NANDRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the NAND of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve True if one or more of the below resolves False, otherwise resolve False"

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) and self.rule2._value(market))


@define(slots=False)
class NeitherRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the NOR of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve False if either of the below resolve to True, otherwise resolve True"

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) or self.rule2._value(market))


@define(slots=False)
class XORRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the XOR of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve False if the below resolve to the same value, otherwise resolve True"

    def _value(self, market: Market) -> bool:
        return bool(bool(self.rule1._value(market)) ^ bool(self.rule2._value(market)))


@define(slots=False)
class XNORRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the XNOR of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "Resolve True if the below resolve to the same value, otherwise resolve False"

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) == bool(self.rule2._value(market))


@define(slots=False)
class ImpliesRule(BinaryRule[Optional[BinaryResolution]]):
    """Return the implication of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = (
        "Resolve True if the next line resolves False, otherwise resolves to the value of the item after"
    )

    def _value(self, market: Market) -> bool:
        return not self.rule1._value(market) or bool(self.rule2._value(market))


@define(slots=False)
class ConditionalRule(BinaryRule[BinaryResolution]):
    """Cancels if the premise is false, and resolve to another value otherwise."""

    _explainer_stub: ClassVar[str] = (
        "Cancels if the next line resolves False, otherwise resolves to the value of the item after"
    )

    def _value(self, market: Market) -> BinaryResolution:
        f_val1 = parallel(self.rule1._value, market)
        f_val2 = parallel(self.rule2._value, market)
        if not f_val1.result():
            return "CANCEL"
        return f_val2.result()


@define(slots=False)
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


@define(slots=False)
class ResolveToValue(Generic[T], Rule[T]):
    """Resolve to a pre-specified value."""

    resolve_value: T

    def _value(self, market: Market) -> T:
        return self.resolve_value

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the specific value {self.resolve_value}\n"


@define(slots=False)
class ModulusRule(BinaryRule[PseudoNumericResolution]):
    """Return the modulus of two other DoResolveRules."""

    _explainer_stub: ClassVar[str] = "A mod B, where A is the next line and B the line after"

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        val1, val2 = self.rule1._value(market), self.rule2._value(market)
        if val1 == "CANCEL" or val2 == "CANCEL":
            return "CANCEL"
        return val1 % val2


@define(slots=False)
class AdditiveRule(VariadicRule[PseudoNumericResolution]):
    """Return the sum of many other Rules."""

    _explainer_stub: ClassVar[str] = "The sum of the below"

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        """Return the sum of the underlying rules."""
        ret: float = 0
        futures = [parallel(rule.value, market, format='PSEUDO_NUMERIC') for rule in self.rules]
        for f_rule in futures:
            val = cast(
                PseudoNumericResolution,
                f_rule.result()
            )
            if val == "CANCEL":
                return "CANCEL"
            ret += val
        return ret


@define(slots=False)
class MultiplicitiveRule(VariadicRule[PseudoNumericResolution]):
    """Return the product of many other Rules."""

    _explainer_stub: ClassVar[str] = "The product of the below"

    def _value(self, market: Market) -> Literal["CANCEL"] | float:
        """Return the product of the underlying rules."""
        ret: float = 1
        futures = [parallel(rule.value, market, format='PSEUDO_NUMERIC') for rule in self.rules]
        for f_rule in futures:
            val = cast(
                PseudoNumericResolution,
                f_rule.result()
            )
            if val == "CANCEL":
                return "CANCEL"
            ret *= val
        return ret


@define(slots=False)
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
        """Ensure that we select a different method depending on the type of range that's requested."""
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
            assert isinstance(market.market.pool, Mapping)
            items = [(int(idx), float(obj)) for idx, obj in market.market.pool.items() if int(idx) >= self.start]
            self.args = (range(self.start, self.start + len(items)), )
            self.kwargs["weights"] = [prob for _, prob in items]
        return cast(int, super()._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolve to a random index, given some original seed. This one operates on a "
        if self.method == 'rand"range':
            ret += f"fixed range of integers in ({self.start} <= x < {self.size}).\n"
        else:
            ret += f"dynamic range based on the current pool and probabilities, but starting at {self.start}.\n"
        return ret


@define(slots=False)
class ResolveMultipleValues(ResolutionValueRule):
    """Resolve to multiple values with different shares."""

    shares: MutableSequence[tuple[ResolutionValueRule, float]] = Factory(list)

    def _value(self, market: Market) -> FreeResponseResolution | MultipleChoiceResolution:
        ret: DefaultDict[int, float] = defaultdict(float)
        for rule, part in self.shares:
            val = cast(Dict[Union[str, int], Future[float]], parallel(rule.value, market, format='FREE_RESPONSE'))
            for idx, value in val.items():
                ret[int(idx)] += value.result() * part
        return normalize_mapping(ret)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}Resolves to the weighted union of multiple other values.\n"
        indent += 1
        for rule, weight in self.shares:
            ret += f"{'  ' * indent} - At a weight of {weight}\n"
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env: ModJSONDict) -> 'ResolveMultipleValues':
        """Take a dictionary and return an instance of the associated class."""
        env_copy: ModJSONDict = {**env}
        shares: MutableSequence[tuple[ResolutionValueRule | tuple[str, ModJSONDict], float]] = (
            env.get('shares', [])  # type: ignore[assignment]
        )
        new_shares = []
        for rule, weight in shares:
            try:
                type_, kwargs = cast(Tuple[str, ModJSONDict], rule)
                new_rule = get_rule(type_).from_dict(kwargs)
                new_shares.append((new_rule, weight))
            except Exception:
                pass
        env_copy['shares'] = new_shares  # type: ignore
        return super().from_dict(env_copy)
