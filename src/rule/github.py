from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from typing import TYPE_CHECKING, cast

from github3 import GitHub
from github3 import login as gh_login

from ..util import require_env, time_cache
from . import DoResolveRule, ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Optional

    from ..market import Market


def unauth_login() -> GitHub:
    """Return an unauthorized login to GitHub."""
    return GitHub()


@time_cache()
@require_env('GithubAccessToken', 'GithubUsername')
def login() -> GitHub:
    """Return an authorized login to GitHub."""
    return gh_login(username=getenv('GithubUsername'), token=getenv('GithubAccessToken'))


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

    @time_cache()
    @require_env("GithubAccessToken", "GithubUsername")
    def _value(self, market: Market) -> bool:
        """Return True if the issue is closed or the PR is merged, otherwise False."""
        issue = login().issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        return issue.state != 'open' or (pr is not None and pr.merged)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If either of the conditions below are True (-> {self.value(market)})\n"
        indent += 1
        issue = login().issue(self.owner, self.repo, self.number)
        ret += f"{'  ' * indent}- If the state of the pull request is not open (-> {issue.state})\n"
        pr = issue.pull_request()
        ret += f"{'  ' * indent}- If the pull request is merged (-> {pr is not None and pr.merged})\n"
        return ret


@dataclass
class ResolveToPR(ResolutionValueRule):
    """Resolve to True if the PR is merged, otherwise False."""

    owner: str
    repo: str
    number: int

    @time_cache()
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

    @time_cache()
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
