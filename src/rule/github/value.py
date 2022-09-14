from dataclasses import dataclass
from datetime import datetime
from os import getenv
from typing import Optional

import requests

from .. import ResolutionValueRule
from ...market import Market
from ...util import require_env


@dataclass
class ResolveToPR(ResolutionValueRule):
    owner: str
    repo: str
    number: int

    @require_env("GithubAPIKey")
    def _value(self, market: Market) -> bool:
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
    def _value(self, market: Market) -> float:
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
