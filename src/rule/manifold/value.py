from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from pymanifold.lib import ManifoldClient

from ...util import fibonacci, market_to_answer_map, normalize_mapping, pool_to_number_cpmm1, prob_to_number_cpmm1
from .. import ResolutionValueRule
from . import ManifoldMarketMixin

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Literal

    from pymanifold.types import Market as APIMarket

    from ... import FreeResponseResolution, MultipleChoiceResolution
    from ...market import Market


@dataclass
class OtherMarketValue(ResolutionValueRule, ManifoldMarketMixin):
    def _value(self, market: Market) -> float | dict[Any, float]:
        mkt = self.api_market()
        if mkt.outcomeType == "BINARY":
            return self._binary_value(market, mkt)
        elif mkt.outcomeType == "PSEUDO_NUMERIC":
            return prob_to_number_cpmm1(
                mkt.resolutionProbability,
                float(mkt.min or 0),
                float(mkt.max or 0),
                mkt.isLogScale
            )
        raise NotImplementedError("Doesn't seem to be reported in the API")

    def _binary_value(self, market: Market, mkt: APIMarket) -> bool | float:
        if mkt.resolution == "YES":
            return True
        elif mkt.resolution == "NO":
            return False
        return float(mkt.resolutionProbability) * 100

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current market value of {self.id_} ({self.api_market().question}).\n"


class CurrentValueRule(ResolutionValueRule):
    """Resolve to the current market-consensus value."""

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


@dataclass
class ResolveToUserProfit(CurrentValueRule):
    """Resolve to the currently reported profit of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['profitCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} profit of user {self.user}.\n"


@dataclass
class ResolveToUserCreatedVolume(CurrentValueRule):
    """Resolve to the currently reported created market volume of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['creatorVolumeCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
