from dataclasses import dataclass
from math import log10
from typing import Any, Dict, Literal, Union, cast

from pymanifold.lib import ManifoldClient

from .. import ResolutionValueRule
from ...market import Market


class CurrentValueRule(ResolutionValueRule):
    def _value(self, market: Market) -> Union[float, Dict[Any, float]]:
        if market.market.outcomeType == "BINARY":
            return market.market.probability * 100
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            pno = market.market.p * market.market.pool['NO']
            probability = (pno / ((1 - market.market.p) * market.market.pool['YES'] + pno))
            start = float(market.market.min or 0)
            end = float(market.market.max or 0)
            if market.market.isLogScale:
                logValue = log10(end - start + 1) * probability
                return max(start, min(end, 10**logValue + start - 1))
            else:
                return max(start, min(end, start + (end - start) * probability))
        elif market.market.outcomeType == "FREE_RESPONSE":
            return {
                answer: float(answer['probability'])
                for answer in market.market.answers
            }
        elif market.market.outcomeType == "MULTIPLE_CHOICE":
            return {
                answer: float(market.market.pool[answer])
                for answer in market.market.pool
            }
        raise ValueError()

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


class RoundValueRule(CurrentValueRule):
    def _value(self, market: Market) -> float:
        if market.market.outcomeType in ("MULTIPLE_CHOICE", "FREE_RESPONSE"):
            raise RuntimeError()
        elif market.market.outcomeType == "BINARY":
            return bool(round(market.market.probability))
        return round(cast(float, super()._value(market)))

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to round(MKT).\n"


@dataclass
class PopularValueRule(ResolutionValueRule):
    size: int = 1

    def _value(self, market: Market):
        if market.market.outcomeType == "FREE_RESPONSE":
            answers = market.market.answers.copy()
            final_answers = []
            for _ in range(self.size):
                next_answer = max(answers, key=lambda x: x['probability'])
                answers.remove(next_answer)
                final_answers.append(next_answer)
            total = sum(float(x['probability']) for x in final_answers)
            return {
                answer: float(answer['probability']) / total
                for answer in final_answers
            }
        elif market.market.outcomeType == "MULTIPLE_CHOICE":
            answers = market.market.pool.copy()
            final_answers = []
            for _ in range(self.size):
                next_answer = max(answers, key=lambda x: answers[x])
                del answers[next_answer]
                final_answers.append(next_answer)
            total = sum(float(market.market.pool[x]) for x in final_answers)
            return {
                answer: float(market.market.pool[answer]) / total
                for answer in final_answers
            }
        raise ValueError()

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the {self.size} most probable answers, weighted by their probability.\n"


@dataclass
class ResolveToUserProfit(CurrentValueRule):
    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return user['profitCached'][self.field]

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} profit of user {self.user}.\n"


@dataclass
class ResolveToUserCreatedVolume(CurrentValueRule):
    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: Market) -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return user['creatorVolumeCached'][self.field]

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
