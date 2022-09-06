from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import log10
from os import getenv
from random import Random
from typing import MutableSequence, Tuple, cast, Any, DefaultDict, Dict, Sequence, Optional

import requests

from . import require_env, Rule


class DoResolveRule(Rule):
    """The subtype of rule which determines if a market should resolve, returning a bool."""

    def value(self, market) -> bool:
        raise NotImplementedError()


@dataclass
class NegateRule(DoResolveRule):
    """Negate another DoResolveRule."""

    child: DoResolveRule

    def value(self, market) -> bool:
        return not self.child.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return (
            f"{'  ' * indent}- If the rule below resolves False\n" +
            self.child.explain_abstract(indent + 1, **kwargs)
        )

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        if "child" in env:
            try:
                type_, kwargs = env["child"]
                env["child"] = globals().get(type_).from_dict(kwargs)
            except Exception:
                pass
        return super().from_dict(env)


@dataclass
class EitherRule(DoResolveRule):
    """Return the OR of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) or self.rule2.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = globals().get(type_).from_dict(kwargs)
                except Exception:
                    pass
        return super().from_dict(env)


@dataclass
class BothRule(DoResolveRule):
    """Return the AND of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) and self.rule2.value(market)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = globals().get(type_).from_dict(kwargs)
                except Exception:
                    pass
        return super().from_dict(env)


@dataclass
class ResolveAtTime(DoResolveRule):
    """Return True if the specified time is in the past."""

    resolve_at: datetime

    def value(self, market) -> bool:
        try:
            return datetime.utcnow() >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the current time is past {self.resolve_at}\n"


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

# curl \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: token <TOKEN>" \
#   https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER

    def value(self, market) -> bool:
        response = requests.get(
            url=f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}",
            headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
        )
        json = response.json()
        return "pull_request" in json and json["pull_request"].get("merged_at") is not None

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"


class ResolutionValueRule(Rule):
    """The subtype of rule which determines what a market should resolve to."""

    def value(self, market, format='BINARY'):
        ret = self._value(market)
        if ret is None:
            return ret
        elif format in ('BINARY', 'PSEUDO_NUMERIC'):
            if isinstance(ret, (int, float, )):
                return ret
            elif isinstance(ret, str):
                if ret == 'CANCEL':
                    return ret
                return int(ret)
            elif isinstance(ret, Sequence):
                if len(ret) == 1:
                    return ret[0]
            elif isinstance(ret, dict):
                if len(ret) == 1:
                    return ret.popitem()[0]
            else:
                raise TypeError(ret, format, market)
        elif format in ('FREE_RESPONSE', 'MULTIPLE_CHOICE'):
            if isinstance(ret, dict):
                return ret
            elif isinstance(ret, str):
                if ret == 'CANCEL':
                    return ret
                return {ret: 1}
            elif isinstance(ret, (int, float, )):
                return {ret: 1}
            elif isinstance(ret, Sequence):
                if len(ret) == 1:
                    return {ret[0]: 1}
            else:
                raise TypeError(ret, format, market)


@dataclass
class ResolveToValue(ResolutionValueRule):
    resolve_value: Any

    def _value(self, market):
        return self.resolve_value

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the specific value {self.resolve_value}\n"


class CurrentValueRule(ResolutionValueRule):
    def _value(self, market) -> float:
        if market.market.outcomeType == "BINARY":
            return market.market.probability * 100
        pno = market.market.p * market.market.pool['NO']
        probability = (pno / ((1 - market.market.p) * market.market.pool['YES'] + pno))
        start = float(market.market.min or 0)
        end = float(market.market.max or 0)
        if market.market.isLogScale:
            logValue = log10(end - start + 1) * probability
            return max(start, min(end, 10**logValue + start - 1))
        else:
            return max(start, min(end, start + (end - start) * probability))

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to the current market value.\n"


class RoundValueRule(CurrentValueRule):
    def _value(self, market) -> float:
        if market.market.outcomeType == "BINARY":
            return bool(round(market.market.probability))
        return round(super()._value(market))

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- Resolves to round(MKT).\n"


@dataclass
class PopularValueRule(ResolutionValueRule):
    size: int = 1

    def _value(self, market):
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
class ResolveRandomSeed(ResolutionValueRule):
    seed: Any
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def _value(self, market) -> float:
        source = Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret


@dataclass
class ResolveRandomIndex(ResolveRandomSeed):
    size: Optional[int] = None
    start: int = 0

    def __init__(self, seed, *args, size=None, start=0, **kwargs):
        self.start = start
        self.size = size
        if size is None:
            method = 'choices'
        else:
            method = 'randrange'
        super().__init__(seed, method, *args, **kwargs)

    def _value(self, market) -> int:
        if self.method == 'randrange':
            self.args = (self.start, self.size)
        else:
            items = [(int(idx), float(obj)) for idx, obj in market.market.pool.items() if int(idx) >= self.start]
            self.args = (range(self.start, self.start + len(items)), )
            self.kwargs["weights"] = [prob for _, prob in items]
        return cast(int, super()._value(market))

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolve to a random index, given some original seed. This one operates on a "
        if self.method == 'randrange':
            ret += f"fixed range of integers in ({self.start} <= x < {self.size}).\n"
        else:
            ret += f"dynamic range based on the current pool and probabilities, but starting at {self.start}.\n"
        return ret


@dataclass
class ResolveMultipleValues(ResolutionValueRule):
    shares: MutableSequence[Tuple[ResolutionValueRule, float]] = field(default_factory=list)

    def _value(self, market) -> Dict[int, float]:
        ret: DefaultDict[int, float] = defaultdict(float)
        for rule, part in self.shares:
            for idx, value in rule.value(market, format='FREE_RESPONSE').items():
                ret[idx] += value * part
            ret.update(rule.value(market, format='FREE_RESPONSE'))
        return ret

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}Resolves to the weighted union of multiple other values.\n"
        indent += 1
        for rule, weight in self.shares:
            ret += f"{'  ' * indent} - At a weight of {weight}\n"
            ret += rule.explain_abstract(indent + 1, **kwargs)
        return ret

    @classmethod
    def from_dict(cls, env):
        """Take a dictionary and return an instance of the associated class."""
        shares: MutableSequence[ResolutionValueRule, float] = env['shares']
        new_shares = []
        for rule, weight in shares:
            try:
                type_, kwargs = rule
                new_rule = globals().get(type_).from_dict(kwargs)
                new_shares.append((new_rule, weight))
            except Exception:
                pass
        env['shares'] = new_shares
        return super().from_dict(env)


@dataclass
class ResolveToPR(ResolutionValueRule):
    owner: str
    repo: str
    number: int

    @require_env("GithubAPIKey")
    def _value(self, market) -> bool:
        response = requests.get(
            url=f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}",
            headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
        )
        json = response.json()
        return "pull_request" in json and json["pull_request"].get("merged_at") is not None

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret


@dataclass
class ResolveToPRDelta(ResolutionValueRule):
    owner: str
    repo: str
    number: int
    start: datetime

    @require_env("GithubAPIKey")
    def _value(self, market) -> float:
        response = requests.get(
            url=f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}",
            headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
        )
        json = response.json()
        if "pull_request" not in json or json["pull_request"].get("merged_at") is None:
            return market.market.max
        delta = datetime.fromisoformat(json["pull_request"].get("merged_at").rstrip('Z')) - self.start
        return delta.days + (delta.seconds / (24 * 60 * 60))

    def explain_abstract(self, indent=0, max_: Optional[float] = None, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += (f"{'  ' * indent}- If the PR is merged, resolve to the number of days between {self.start} and the "
                "resolution time.\n")
        ret += f"{'  ' * indent}- Otherwise, resolve to MAX"
        if max_ is not None:
            ret += f" ({max_})"
        ret += ".\n"
        return ret
