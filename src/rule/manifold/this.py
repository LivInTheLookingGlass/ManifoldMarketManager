from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import TYPE_CHECKING, cast

from ...util import fibonacci, market_to_answer_map, normalize_mapping, pool_to_number_cpmm1, time_cache
from .. import DoResolveRule, ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ... import FreeResponseResolution, MultipleChoiceResolution
    from ...market import Market


class ThisMarketClosed(DoResolveRule):
    @time_cache()
    def _value(self, market: Market) -> bool:
        return bool(market.market.closeTime < time() * 1000)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If this market reaches its close date\n"


class CurrentValueRule(ResolutionValueRule):
    """Resolve to the current market-consensus value."""

    @time_cache()
    def _value(self, market: Market) -> float | dict[Any, float]:
        if market.market.outcomeType == "BINARY":
            return cast(float, market.market.probability * 100)
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            return pool_to_number_cpmm1(
                market.market.pool['YES'],
                market.market.pool['NO'],
                market.market.p,
                float(market.market.min or 0),
                float(market.market.max or 0),
                market.market.isLogScale
            )
        return market_to_answer_map(market)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


@dataclass
class FibonacciValueRule(ResolutionValueRule):
    """Resolve each value with a fibonacci weight, ranked by probability."""

    exclude: set[int] = field(default_factory=set)
    min_rewarded: float = 0.0001

    @time_cache()
    def _value(self, market: Market) -> float | dict[Any, float]:
        items = market_to_answer_map(market, self.exclude, (lambda id_, probability: probability < self.min_rewarded))
        rank = sorted(items, key=items.__getitem__)
        ret = {item: fib for item, fib in zip(rank, fibonacci())}
        return normalize_mapping(ret)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Weight each* answer to the fibonacci rank of their probability\n"
        block = '  ' * (indent + 1)
        ret += f"{block}- Filter out IDs in {self.exclude}, probabilities below {self.min_rewarded * 100}%\n"
        ret += f"{block}- Sort by probability\n"
        ret += f"{block}- Iterate over this and the fibonacci numbers in lockstep. Those are the weights\n"
        return ret


class RoundValueRule(CurrentValueRule):
    """Resolve to the current market-consensus value, but rounded."""

    @time_cache()
    def _value(self, market: Market) -> float:
        if market.market.outcomeType in ("MULTIPLE_CHOICE", "FREE_RESPONSE"):
            raise RuntimeError()
        elif market.market.outcomeType == "BINARY":
            return bool(round(market.market.probability))
        return round(cast(float, super()._value(market)))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to round(MKT).\n"


@dataclass
class PopularValueRule(ResolutionValueRule):
    """Resolve to the n most likely market-consensus values, weighted by their probability."""

    size: int = 1

    @time_cache()
    def _value(self, market: Market) -> FreeResponseResolution | MultipleChoiceResolution:
        answers = market_to_answer_map(market)
        final_answers: dict[int, float] = {}
        for _ in range(self.size):
            next_answer = max(answers, key=answers.__getitem__)
            final_answers[next_answer] = answers[next_answer]
            del answers[next_answer]
        return normalize_mapping(final_answers)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the {self.size} most probable answers, weighted by their probability.\n"
