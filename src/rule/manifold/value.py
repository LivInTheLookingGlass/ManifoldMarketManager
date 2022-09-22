from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Literal, Union, cast

from pymanifold.lib import ManifoldClient

from ...util import fibonacci, pool_to_number
from ... import FreeResponseResolution, MultipleChoiceResolution
from .. import ResolutionValueRule

if TYPE_CHECKING:
    from ...market import Market


class CurrentValueRule(ResolutionValueRule):
    """Resolve to the current market-consensus value."""

    def _value(self, market: 'Market') -> Union[float, Dict[Any, float]]:
        if market.market.outcomeType == "BINARY":
            return cast(float, market.market.probability * 100)
        elif market.market.outcomeType == "PSEUDO_NUMERIC":
            return pool_to_number(
                market.market.pool['YES'],
                market.market.pool['NO'],
                market.market.p,
                float(market.market.min or 0),
                float(market.market.max or 0),
                market.market.isLogScale
            )
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

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


@dataclass
class FibonacciValueRule(ResolutionValueRule):
    """Resolve each value with a fibonacci weight, ranked by probability."""

    start: int = 0
    min_rewarded: float = 0.0001

    def _value(self, market: 'Market') -> Union[float, Dict[Any, float]]:
        if market.market.outcomeType == "FREE_RESPONSE":
            items = {
                int(answer['id']): float(answer['probability'])
                for answer in market.market.answers
            }
        elif market.market.outcomeType == "MULTIPLE_CHOICE":
            # TODO: reimplement dpm-2 math so this is actually by probability
            pool = {
                int(answer): float(market.market.pool[answer])
                for answer in market.market.pool
            }
            s_total = sum(shares**2 for shares in pool)
            items = {key: shares**2 / s_total for key, shares in pool.items()}
        else:
            raise TypeError()

        rank = sorted(filter(self.start.__le__, items), key=items.__getitem__)
        ret = {item: fib for item, fib in zip(rank, fibonacci())}
        total = sum(ret.values())
        return {key: val / total for key, val in ret.items()}

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Weight each* answer to the fibonacci rank of their probability\n"
        block = '  ' * (indent + 1)
        ret += f"{block}- Filter out indices below {self.start}, probabilities below {self.min_rewarded * 100}%\n"
        ret += f"{block}- Sort by probability\n"
        ret += f"{block}- Iterate over this and the fibonacci numbers in lockstep. Those are the weights\n"
        return ret


class RoundValueRule(CurrentValueRule):
    """Resolve to the current market-consensus value, but rounded."""

    def _value(self, market: 'Market') -> float:
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

    def _value(self, market: 'Market') -> Union[FreeResponseResolution, MultipleChoiceResolution]:
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

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the {self.size} most probable answers, weighted by their probability.\n"


@dataclass
class ResolveToUserProfit(CurrentValueRule):
    """Resolve to the currently reported profit of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: 'Market') -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['profitCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} profit of user {self.user}.\n"


@dataclass
class ResolveToUserCreatedVolume(CurrentValueRule):
    """Resolve to the currently reported created market volume of a user."""

    user: str
    field: Literal["allTime", "daily", "weekly", "monthly"] = "allTime"

    def _value(self, market: 'Market') -> float:
        user = ManifoldClient()._get_user_raw(self.user)
        return cast(float, user['creatorVolumeCached'][self.field])

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- Resolves to the current reported {self.field} market volume created by {self.user}.\n"
