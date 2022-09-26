from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from .. import ResolutionValueRule
from . import login

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Optional

    from ...market import Market


@dataclass
class ResolveToPR(ResolutionValueRule):
    """Resolve to True if the PR is merged, otherwise False."""

    owner: str
    repo: str
    number: int

    def _value(self, market: Market) -> bool:
        issue = login().issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        return pr is not None and pr.merged

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        issue = login().issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- Is the pull request is merged? (-> {merge_time or 'Not yet merged'} -> "
                f"{merge_time is not None})\n")


@dataclass
class ResolveToPRDelta(ResolutionValueRule):
    """Resolve to the fractional number of days between start and merged date or, if not merged, MAX."""

    owner: str
    repo: str
    number: int
    start: datetime

    def _value(self, market: Market) -> float:
        issue = login().issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None or pr.merged_at is None:
            return cast(float, market.market.max)
        delta = cast(datetime, pr.merged_at) - self.start.replace(tzinfo=timezone.utc)
        return delta.days + (delta.seconds / (24 * 60 * 60))

    def _explain_abstract(self, indent: int = 0, max_: Optional[float] = None, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += (f"{'  ' * indent}- If the PR is merged, resolve to the number of days between {self.start} and the "
                "resolution time.\n")
        ret += f"{'  ' * indent}- Otherwise, resolve to MAX"
        if max_ is not None:
            ret += f" ({max_})"
        ret += ".\n"
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        issue = login().issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- How long after {self.start} was the pull request is merged? (-> "
                f"{merge_time or 'Not yet merged'} -> {self.value(market)})\n")
