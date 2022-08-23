from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from os import getenv
from typing import cast, Any, DefaultDict, Dict, Sequence, Optional
import random

import requests

from . import require_env, Rule


class DoResolveRule(Rule):
    def value(self, market) -> bool:
        raise NotImplementedError()


@dataclass
class NegateRule(DoResolveRule):
    child: DoResolveRule

    def value(self, market) -> bool:
        return not self.child.value(market)


@dataclass
class EitherRule(DoResolveRule):
    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) or self.rule2.value(market)


@dataclass
class BothRule(DoResolveRule):
    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market) -> bool:
        return self.rule1.value(market) and self.rule2.value(market)


@dataclass
class ResolveAtTime(DoResolveRule):
    resolve_at: datetime

    def value(self, market) -> bool:
        try:
            return datetime.utcnow() >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at


@dataclass
class ResolveWithPR(DoResolveRule):
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


class ResolutionValueRule(Rule):
    def __hash__(self) -> int:
        # yes, I know this is technically unsafe, but they won't
        return hash((type(self), id(self)))

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

    def __hash__(self) -> int:
        # yes, I know this is technically unsafe, but they won't mutuate in practice
        return hash((type(self), id(self)))

    def _value(self, market):
        return self.resolve_value


@dataclass
class ResolveRandomSeed(ResolutionValueRule):
    seed: Any
    method: str = 'random'
    rounds: int = 1
    args: Sequence[Any] = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        # yes, I know this is technically unsafe, but they won't mutuate in practice
        return hash((type(self), id(self)))

    def _value(self, market) -> float:
        source = random.Random(self.seed)
        method = getattr(source, self.method)
        for _ in range(self.rounds):
            ret = method(*self.args, **self.kwargs)
        return ret


@dataclass
class ResolveRandomIndex(ResolveRandomSeed):
    size: Optional[int] = None
    start: int = 0

    def __hash__(self) -> int:
        # yes, I know this is technically unsafe, but they won't mutuate in practice
        return hash((type(self), id(self)))

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


@dataclass
class ResolveMultipleValues(ResolutionValueRule):
    shares: DefaultDict[ResolutionValueRule, float] = field(default_factory=lambda: defaultdict(float))

    def _value(self, market) -> Dict[int, float]:
        ret: DefaultDict[int, float] = defaultdict(float)
        for rule, part in self.shares.items():
            for idx, value in rule.value(market, format='FREE_RESPONSE').items():
                ret[idx] += value * part
            ret.update(rule.value(market, format='FREE_RESPONSE'))
        return ret


@dataclass
class ResolveToPR(ResolutionValueRule):
    owner: str
    repo: str
    number: int

# curl \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: token <TOKEN>" \
#   https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER

    @require_env("GithubAPIKey")
    def _value(self, market) -> bool:
        response = requests.get(
            url=f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}",
            headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
        )
        json = response.json()
        return "pull_request" in json and json["pull_request"].get("merged_at") is not None


@dataclass
class ResolveToPRDelta(ResolutionValueRule):
    owner: str
    repo: str
    number: int
    start: datetime

# curl \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: token <TOKEN>" \
#   https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER

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
