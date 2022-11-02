"""Contain rules that reference the market that is calling them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Union, cast

from attrs import Factory, define

from ... import Rule
from ...consts import (BinaryResolution, FreeResponseResolution, MultipleChoiceResolution, Outcome,
                       PseudoNumericResolution, T)
from ...util import fibonacci, market_to_answer_map, normalize_mapping
from . import ManifoldMarketMixin
from .other import OtherMarketClosed, OtherMarketUniqueTraders, OtherMarketValue

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, ClassVar, Optional

    from pymanifold.lib import ManifoldClient
    from pymanifold.types import Market as APIMarket

    from ...market import Market


@define(slots=False)
class ThisToOtherConverter(ManifoldMarketMixin):
    """A mixin class that converts market accesses to reuse `other` code."""

    id_: str = "N/A"

    def api_market(self, client: Optional[ManifoldClient] = None, market: Optional[Market] = None) -> APIMarket:
        """Return an APIMarket object associated with this rule's market."""
        assert market is not None
        market.refresh()
        return market.market


@define(slots=False)
class ThisMarketClosed(OtherMarketClosed, ThisToOtherConverter):
    """A rule that checks whether its associated market is closed."""

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return "If this market reaches its close date\n"


@define(slots=False)
class CurrentValueRule(OtherMarketValue[T], ThisToOtherConverter):
    """Resolve to the current market-consensus value."""

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return "Resolves to the current market value\n"


@define(slots=False)
class UniqueTradersRule(ThisToOtherConverter, OtherMarketUniqueTraders):
    """Resolve to the current number of unique traders."""

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return "Resolves to the current number of unique traders\n"


@define(slots=False)
class FibonacciValueRule(Rule[Union[float, Mapping[int, float]]]):
    """Resolve each value with a fibonacci weight, ranked by probability."""

    exclude: set[int] = Factory(set)
    min_rewarded: float = 0.0001

    def _value(self, market: Market) -> float | dict[int, float]:
        market.refresh()
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


class RoundValueRule(CurrentValueRule[Union[BinaryResolution, PseudoNumericResolution]]):
    """Resolve to the current market-consensus value, but rounded."""

    _explainer_stub: ClassVar[str] = "Resolves to round(MKT)"

    def _value(self, market: Market) -> float:
        if market.market.outcomeType in Outcome.MC_LIKE():
            raise RuntimeError()
        elif market.market.outcomeType == Outcome.BINARY:
            assert market.market.probability
            return bool(round(market.market.probability))
        return round(cast(float, super()._value(market)))


@define(slots=False)
class PopularValueRule(Rule[Union[MultipleChoiceResolution, FreeResponseResolution]]):
    """Resolve to the n most likely market-consensus values, weighted by their probability."""

    size: int = 1

    def _value(self, market: Market) -> FreeResponseResolution | MultipleChoiceResolution:
        market.refresh()
        answers = market_to_answer_map(market)
        final_answers: dict[int, float] = {}
        try:
            for _ in range(self.size):
                next_answer = max(answers, key=answers.__getitem__)
                final_answers[next_answer] = answers[next_answer]
                del answers[next_answer]
        except ValueError as e:

            if "arg is an empty sequence" not in e.args[0]:
                raise
        return normalize_mapping(final_answers)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the {self.size} most probable answers, weighted by their probability.\n"
