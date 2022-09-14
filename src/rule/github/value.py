from dataclasses import dataclass
from datetime import datetime
from os import getenv
from typing import Optional

from github3 import login

from .. import ResolutionValueRule
from ...market import Market
from ...util import require_env


@dataclass
class ResolveToPR(ResolutionValueRule):
    owner: str
    repo: str
    number: int

    @require_env('GithubAPIKey')
    def _value(self, market: Market) -> bool:
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        return pr is not None and pr.merged

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret

    def explain_specific(self, market: Market, indent=0) -> str:
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- Is the pull request is merged? (-> {merge_time or 'Not yet merged'} -> "
                f"{merge_time is not None})\n")


@dataclass
class ResolveToPRDelta(ResolutionValueRule):
    owner: str
    repo: str
    number: int
    start: datetime

    @require_env('GithubAPIKey')
    def _value(self, market: Market) -> float:
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None or pr.merged_at is None:
            return market.market.max
        delta = pr.merged_at - self.start
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

    def explain_specific(self, market: Market, indent=0) -> str:
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- How long after {self.start} was the pull request is merged? (-> "
                f"{merge_time or 'Not yet merged'} -> {self.value(market)})\n")
