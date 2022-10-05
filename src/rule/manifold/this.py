from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Mapping, cast

from attrs import Factory, define

from ...util import fibonacci, market_to_answer_map, normalize_mapping, pool_to_number_cpmm1
from .. import DoResolveRule, ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ... import FreeResponseResolution, MultipleChoiceResolution
    from ...market import Market


@define(slots=False)
class ThisMarketClosed(DoResolveRule):
    def _value(self, market: Market) -> bool:
        assert market.market.closeTime is not None
        return bool(market.market.closeTime < time() * 1000)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If this market reaches its close date\n"


@define(slots=False)
class CurrentValueRule(ResolutionValueRule):
    """Resolve to the current market-consensus value."""

    def _value(self, market: Market) -> float | dict[Any, float]:
        if market.market.outcomeType == "BINARY":
            assert market.market.probability is not None
            return market.market.probability * 100
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            assert isinstance(market.market.pool, Mapping)
            assert market.market.p
            return pool_to_number_cpmm1(
                market.market.pool['YES'],
                market.market.pool['NO'],
                market.market.p,
                float(market.market.min or 0),
                float(market.market.max or 0),
                bool(market.market.isLogScale)
            )
        return market_to_answer_map(market)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


@define(slots=False)
class FibonacciValueRule(ResolutionValueRule):
    """Resolve each value with a fibonacci weight, ranked by probability."""

    exclude: set[int] = Factory(set)
    min_rewarded: float = 0.0001

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


@define(slots=False)
class RoundValueRule(CurrentValueRule):
    """Resolve to the current market-consensus value, but rounded."""

    def _value(self, market: Market) -> float:
        if market.market.outcomeType in ("MULTIPLE_CHOICE", "FREE_RESPONSE"):
            raise RuntimeError()
        elif market.market.outcomeType == "BINARY":
            assert market.market.probability
            return bool(round(market.market.probability))
        return round(cast(float, super()._value(market)))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to round(MKT).\n"


@define(slots=False)
class PopularValueRule(ResolutionValueRule):
    """Resolve to the n most likely market-consensus values, weighted by their probability."""

    size: int = 1

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
