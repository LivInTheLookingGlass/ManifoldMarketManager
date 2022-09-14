from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import get_issue
from .. import ResolutionValueRule
from ...market import Market


@dataclass
class ResolveToPR(ResolutionValueRule):
    owner: str
    repo: str
    number: int

    def _value(self, market: Market) -> bool:
        json = get_issue(self.owner, self.repo, self.number)
        return "pull_request" in json and json["pull_request"].get("merged_at") is not None

    def explain_abstract(self, indent=0, **kwargs) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret

    def explain_specific(self, market: Market, indent=0) -> str:
        json = get_issue(self.owner, self.repo, self.number)
        merge_time = json.get('pull_request', {}).get('merged_at')
        return (f"{'  ' * indent}- Is the pull request is merged? (-> {merge_time or 'Not yet merged'} -> "
                f"{merge_time is not None})\n")


@dataclass
class ResolveToPRDelta(ResolutionValueRule):
    owner: str
    repo: str
    number: int
    start: datetime

    def _value(self, market: Market) -> float:
        json = get_issue(self.owner, self.repo, self.number)
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

    def explain_specific(self, market: Market, indent=0) -> str:
        json = get_issue(self.owner, self.repo, self.number)
        merge_time = json.get('pull_request', {}).get('merged_at')
        return (f"{'  ' * indent}- How long after {self.start} was the pull request is merged? (-> "
                f"{merge_time or 'Not yet merged'} -> {self.value(market)})\n")
