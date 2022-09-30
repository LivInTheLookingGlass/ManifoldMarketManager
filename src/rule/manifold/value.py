from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from pymanifold.lib import ManifoldClient

from ...util import (fibonacci, market_to_answer_map, normalize_mapping, pool_to_number_cpmm1, prob_to_number_cpmm1,
                     round_sig_figs, time_cache)
from .. import ResolutionValueRule
from ..generic.value import ResolveRandomSeed
from . import ManifoldMarketMixin

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Literal

    from pymanifold.types import Market as APIMarket

    from ... import BinaryResolution, FreeResponseResolution, MultipleChoiceResolution
    from ...market import Market


@dataclass
class OtherMarketValue(ManifoldMarketMixin, ResolutionValueRule):
    @time_cache()
    def _value(self, market: Market) -> BinaryResolution:
        mkt = self.api_market()
        if mkt.resolution == "CANCEL":
            return "CANCEL"
        elif mkt.outcomeType == "BINARY":
            return self._binary_value(market, mkt) * 100
        elif mkt.outcomeType == "PSEUDO_NUMERIC":
            return prob_to_number_cpmm1(
                self._binary_value(market, mkt),
                float(mkt.min or 0),
                float(mkt.max or 0),
                mkt.isLogScale
            )
        raise NotImplementedError("Doesn't seem to be reported in the API")

    def _binary_value(self, market: Market, mkt: APIMarket) -> float:
        if mkt.isResolved:
            if mkt.resolution == "YES":
                return True
            elif mkt.resolution == "NO":
                return False
            return float(mkt.resolutionProbability)
        return float(mkt.probability)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return (f"{'  ' * indent}- Resolved (or current, if not resolved) value of `{self.id_}` "
                f"({self.api_market().question}).\n")

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = (f"{'  ' * indent}- Resolved (or current, if not resolved) value of `{self.id_}` "
               f"({self.api_market().question}) (-> ")
        mkt = self.api_market()
        val = self._value(market)
        if val == "CANCEL":
            ret += "CANCEL)\n"
        else:
            ret += f"{round_sig_figs(val, sig_figs)}"
        if mkt.outcomeType == "BINARY":
            ret += "%"
        return ret + ")\n"


@dataclass
class AmplifiedOddsRule(OtherMarketValue, ResolveRandomSeed):
    """Immitate the amplified odds scheme deployed by @Tetraspace.

    This rule resolves YES if the referenced market resolves YES.

    If the referenced market resolves NO, I will get a random number using a predetermined seed. If it is less than
    `1 / a`, I will resolve NO. Otherwise, I will resolve N/A. This means that, for this rule, you should treat NO as
    if it is `a` times less likely to happen than it actually is.

    For example, if `a = 100`, and your actual expected outcome is 0.01% YES, 99.99% NO, you should expect this to
    resolve with probabilities 0.01% YES, 0.9999% NO, 98.9901% N/A, which means that your price of a YES share should
    be ~1% (actually 0.99%).

    Some other values, for calibration (using the formula YES' = YES/(YES + (1-YES)/100), where YES' is the price for
    this question, and YES is your actual probability):
    0.02% YES => ~2% YES' (actually 1.96%)
    0.05% YES => ~5% YES' (actually 4.76%)
    0.1% YES => 9% YES'
    0.2% YES => 17% YES'
    0.5% YES => 33% YES'
    1% YES => 50% YES'
    2% YES => 67% YES'
    5% YES => 84% YES'
    10% YES => 92% YES'
    20% YES => 96% YES'
    50% YES => 99% YES'
    100% YES => 100% YES'
    """

    a: int = 1

    @time_cache()
    def _value(self, market: Market) -> BinaryResolution:
        val = OtherMarketValue._binary_value(self, market, self.api_market())
        if val is True:
            return True
        if val is False:
            if ResolveRandomSeed._value(self, market) < (1 / self.a):
                return False
            return "CANCEL"
        return val / (val + (1 - val) / self.a) * 100

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Amplified odds:\n"
        indent += 1
        ret += f"{'  ' * indent}- If the referenced market resolves YES, resolve YES\n"
        ret += super()._explain_abstract(indent + 1, **kwargs)
        ret += f"{'  ' * indent}- If it resolved NO, generate a random number using a predetermined seed\n"
        indent += 1
        a_recip = round_sig_figs(1 / self.a)
        ret += f"{'  ' * indent}- If the number is less than `1 / a` ({self.a} -> ~{a_recip}), resolve NO\n"
        ret += f"{'  ' * indent}- Otherwise, resolve N/A\n"
        indent -= 1
        ret += f"{'  ' * indent}- Otherwise, resolve to the equivalent price of the reference market\n"
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        val = self._value(market)
        ret = f"{'  ' * indent}- Amplified odds: (-> "
        if val == "CANCEL":
            ret += "CANCEL)\n"
        else:
            ret += f"{round_sig_figs(val, 4)}%)\n"
        indent += 1
        ret += f"{'  ' * indent}- If the referenced market resolves True, resolve True\n"
        ret += OtherMarketValue._explain_specific(cast(OtherMarketValue, super()), market, indent + 1, sig_figs)
        ret += f"{'  ' * indent}- If it resolved NO, generate a random number using a predetermined seed\n"
        indent += 1
        a_recip = round_sig_figs(1 / self.a, sig_figs)
        ret += f"{'  ' * indent}- If the number is less than `1 / a` ({self.a} -> ~{a_recip}), resolve NO\n"
        ret += f"{'  ' * indent}- Otherwise, resolve N/A\n"
        indent -= 1
        ret += f"{'  ' * indent}- Otherwise, resolve to the equivalent price of the reference market\n"
        return ret


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


@dataclass
class ResolveToUserProfit(CurrentValueRule):
    """Resolve to the currently reported profit of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    @time_cache()
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

    @time_cache()
    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['creatorVolumeCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
