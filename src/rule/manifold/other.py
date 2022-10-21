"""Contains rules that reference other Manifold markets."""

from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, cast

from attrs import define

from ... import Rule
from ...caching import parallel
from ...consts import BinaryResolution, Outcome, T
from ...util import market_to_answer_map, prob_to_number_cpmm1, round_sig_figs
from .. import DoResolveRule
from ..abstract import ResolveRandomSeed
from . import ManifoldMarketMixin

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from pymanifold.types import Market as APIMarket

    from ...consts import AnyResolution
    from ...market import Market


@define(slots=False)
class OtherMarketClosed(DoResolveRule, ManifoldMarketMixin):
    """A rule that checks whether another market is closed."""

    def _value(self, market: Market) -> bool:
        mkt = self.api_market()
        assert mkt.closeTime is not None
        return bool(mkt.isResolved or (mkt.closeTime < time() * 1000))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If `{self.id_}` closes ({self.api_market().question}).\n"


@define(slots=False)
class OtherMarketResolved(DoResolveRule, ManifoldMarketMixin):
    """A rule that checks whether another market is resolved."""

    def _value(self, market: Market) -> bool:
        return bool(self.api_market().isResolved)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If `{self.id_}` is resolved ({self.api_market().question}).\n"


@define(slots=False)
class OtherMarketValue(ManifoldMarketMixin, Rule[T]):
    """A rule that resolves to the value of another rule."""

    def _value(self, market: Market) -> T:
        mkt = self.api_market()
        if mkt.resolution == "CANCEL":
            ret: AnyResolution = "CANCEL"
        elif mkt.outcomeType == "BINARY":
            ret = self._binary_value(market, mkt) * 100
        elif mkt.outcomeType == "PSEUDO_NUMERIC":
            ret = prob_to_number_cpmm1(
                self._binary_value(market, mkt),
                float(mkt.min or 0),
                float(mkt.max or 0),
                bool(mkt.isLogScale)
            )
        else:
            ret = market_to_answer_map(mkt)
        return cast(T, ret)

    def _binary_value(self, market: Market, mkt: APIMarket | None = None) -> float:
        if mkt is None:
            mkt = self.api_market()
        if mkt.isResolved:
            if mkt.resolution == "YES":
                return True
            elif mkt.resolution == "NO":
                return False
            return cast(float, mkt.resolutionProbability)
        return cast(float, mkt.probability)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return (f"{'  ' * indent}- Resolved (or current, if not resolved) value of `{self.id_}` "
                f"({self.api_market().question}).\n")

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        f_mkt = self.f_api_market()
        f_val = parallel(self._value, market)
        mkt = f_mkt.result()
        ret = (f"{'  ' * indent}- Resolved (or current, if not resolved) value of `{self.id_}` "
               f"({mkt.question}) (-> ")
        val = f_val.result()
        if val == "CANCEL":
            ret += "CANCEL"
        elif mkt.outcomeType == Outcome.PSEUDO_NUMERIC:
            assert isinstance(val, float)
            ret += f"{round_sig_figs(val, sig_figs)}"
        elif mkt.outcomeType == Outcome.BINARY:
            assert isinstance(val, float)
            ret += f"{round_sig_figs(val, sig_figs)}%"
        elif mkt.outcomeType in Outcome.MC_LIKE():
            ret += repr(market_to_answer_map(mkt))
        return ret + ")\n"


@define(slots=False)
class AmplifiedOddsRule(OtherMarketValue[BinaryResolution], ResolveRandomSeed):
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

    def _value(self, market: Market) -> BinaryResolution:
        val = OtherMarketValue._binary_value(self, market)
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
        f_val = parallel(self._value, market)
        other_exp = parallel(OtherMarketValue._explain_specific, self, market, indent + 1, sig_figs)
        ret = f"{'  ' * indent}- Amplified odds: (-> "
        val = f_val.result()
        if val == "CANCEL":
            ret += "CANCEL)\n"
        else:
            ret += f"{round_sig_figs(val, 4)}%)\n"
        indent += 1
        ret += f"{'  ' * indent}- If the referenced market resolves True, resolve True\n"
        ret += other_exp.result()
        ret += f"{'  ' * indent}- If it resolved NO, generate a random number using a predetermined seed\n"
        indent += 1
        a_recip = round_sig_figs(1 / self.a, sig_figs)
        ret += f"{'  ' * indent}- If the number is less than `1 / a` ({self.a} -> ~{a_recip}), resolve NO\n"
        ret += f"{'  ' * indent}- Otherwise, resolve N/A\n"
        indent -= 1
        ret += f"{'  ' * indent}- Otherwise, resolve to the equivalent price of the reference market\n"
        return ret
