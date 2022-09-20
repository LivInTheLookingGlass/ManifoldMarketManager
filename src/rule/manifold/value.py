from dataclasses import dataclass
from math import log10
from typing import Any, Dict, Literal, Union, cast

from pymanifold.lib import ManifoldClient

from ... import FreeResponseResolution, MultipleChoiceResolution
from ...market import Market
from .. import ResolutionValueRule


class CurrentValueRule(ResolutionValueRule):
    """Resolve to the current market-consensus value."""

    def _value(self, market: Market) -> Union[float, Dict[Any, float]]:
        if market.market.outcomeType == "BINARY":
            return cast(float, market.market.probability * 100)
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            pno = market.market.p * market.market.pool['NO']
            probability = (pno / ((1 - market.market.p) * market.market.pool['YES'] + pno))
            start = float(market.market.min or 0)
            end = float(market.market.max or 0)
            ret: float
            if market.market.isLogScale:
                logValue = log10(end - start + 1) * probability
                ret = max(start, min(end, 10**logValue + start - 1))
            else:
                ret = max(start, min(end, start + (end - start) * probability))
            return ret
        elif market.market.outcomeType == "FREE_RESPONSE":
            return {
                cast(str, answer['id']): float(answer['probability'])
                for answer in market.market.answers
            }
        elif market.market.outcomeType == "MULTIPLE_CHOICE":
            # TODO: reimplement dpm-2 math so this is actually by probability
            return {
                answer: float(market.market.pool[answer])
                for answer in market.market.pool
            }
        raise ValueError()

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


class RoundValueRule(CurrentValueRule):
    """Resolve to the current market-consensus value, but rounded."""

    def _value(self, market: Market) -> float:
        if market.market.outcomeType in ("MULTIPLE_CHOICE", "FREE_RESPONSE"):
            raise RuntimeError()
        elif market.market.outcomeType == "BINARY":
            return bool(round(market.market.probability))
        return round(cast(float, super()._value(market)))

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to round(MKT).\n"


@dataclass
class PopularValueRule(ResolutionValueRule):
    """Resolve to the n most likely market-consensus values, weighted by their probability."""

    size: int = 1

    def _value(self, market: Market) -> Union[FreeResponseResolution, MultipleChoiceResolution]:
        if market.market.outcomeType == "FREE_RESPONSE":
            answers = market.market.answers.copy()
            final_answers = []
            for _ in range(self.size):
                next_answer_fr = max(answers, key=lambda x: cast(float, x['probability']))
                answers.remove(next_answer_fr)
                final_answers.append(next_answer_fr)
            total = sum(float(x['probability']) for x in final_answers)
            return {
                cast(str, answer['id']): float(answer['probability']) / total
                for answer in final_answers
            }
        elif market.market.outcomeType == "MULTIPLE_CHOICE":
            # TODO: reimplement dpm-2 math so this is actually by probability
            answers = market.market.pool.copy()
            final_answers = []
            for _ in range(self.size):
                next_answer_mc: str = max(answers, key=lambda x: cast(float, answers[x]))
                del answers[next_answer_mc]
                final_answers.append(next_answer_mc)
            total = sum(float(market.market.pool[x]) for x in final_answers)
            return {
                answer: float(market.market.pool[answer]) / total
                for answer in final_answers
            }
        raise ValueError()

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the {self.size} most probable answers, weighted by their probability.\n"


@dataclass
class ResolveToUserProfit(CurrentValueRule):
    """Resolve to the currently reported profit of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['profitCached'][self.field])

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} profit of user {self.user}.\n"


@dataclass
class ResolveToUserCreatedVolume(CurrentValueRule):
    """Resolve to the currently reported created market volume of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['creatorVolumeCached'][self.field])

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
