"""Contains rules that reference GitHub."""

from __future__ import annotations

from datetime import datetime, timezone
from os import getenv
from typing import TYPE_CHECKING, cast

from attrs import define
from github3 import GitHub
from github3 import login as gh_login

from ..caching import parallel
from ..consts import EnvironmentVariable
from ..util import require_env
from . import DoResolveRule, ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from concurrent.futures import Future
    from typing import Any, Optional

    from github3.issues import Issue
    from github3.pulls import PullRequest

    from ..market import Market


def unauth_login() -> GitHub:
    """Return an unauthorized login to GitHub."""
    return GitHub()


@require_env(EnvironmentVariable.GithubAccessToken, EnvironmentVariable.GithubUsername)
def login() -> GitHub:
    """Return an authorized login to GitHub."""
    return gh_login(username=getenv('GithubUsername'), token=getenv('GithubAccessToken'))


@define(slots=False)
class GitHubIssueMixin:
    """Mixin class to represent a GitHub issue."""

    owner: str
    repo: str
    number: int

    def f_issue(self) -> Future[Issue]:
        """Return a Future object which resolves to the relevant Issue object."""
        return parallel(login().issue, self.owner, self.repo, self.number)

    def f_pr(self) -> Future[PullRequest]:
        """Return a Future object which resolves to the relevant PullRequest object."""
        return parallel(login().pull_request, self.owner, self.repo, self.number)


@define(slots=False)
class ResolveWithPR(DoResolveRule, GitHubIssueMixin):
    """Return True if the specified PR was merged in the past."""

    @require_env(EnvironmentVariable.GithubAccessToken, EnvironmentVariable.GithubUsername)
    def _value(self, market: Market) -> bool:
        """Return True if the issue is closed or the PR is merged, otherwise False."""
        f_issue = self.f_issue()
        f_pr = self.f_pr()
        issue = f_issue.result()
        if issue.state != 'open':
            return True
        pr = f_pr.result()
        return pr is not None and pr.merged

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        f_issue = self.f_issue()
        f_pr = self.f_pr()

        ret = f"{'  ' * indent}- If either of the conditions below are True (-> {self.value(market)})\n"
        indent += 1
        issue = f_issue.result()
        ret += f"{'  ' * indent}- If the state of the pull request is not open (-> {issue.state})\n"
        pr = f_pr.result()
        ret += f"{'  ' * indent}- If the pull request is merged (-> {pr is not None and pr.merged})\n"
        return ret


@define(slots=False)
class ResolveToPR(ResolutionValueRule, GitHubIssueMixin):
    """Resolve to True if the PR is merged, otherwise False."""

    def _value(self, market: Market) -> bool:
        pr = self.f_pr().result()
        return pr is not None and pr.merged

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        pr = self.f_pr().result()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- Is the pull request is merged? (-> {merge_time or 'Not yet merged'} -> "
                f"{merge_time is not None})\n")


@define(slots=False)
class ResolveToPRDelta(ResolutionValueRule, GitHubIssueMixin):
    """Resolve to the fractional number of days between start and merged date or, if not merged, MAX."""

    start: datetime

    def _value(self, market: Market) -> float:
        pr = self.f_pr().result()
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
        pr = self.f_pr().result()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- How long after {self.start} was the pull request is merged? (-> "
                f"{merge_time or 'Not yet merged'} -> {self.value(market)})\n")
