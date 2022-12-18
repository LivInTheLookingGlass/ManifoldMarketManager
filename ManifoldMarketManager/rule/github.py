"""Contains rules that reference GitHub."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from attrs import define
from github3 import GitHub, login

from ..caching import parallel
from ..consts import EnvironmentVariable
from ..util import require_env
from . import DoResolveRule, ResolutionValueRule

if TYPE_CHECKING:  # pragma: no cover
    from concurrent.futures import Future
    from typing import Any, Callable, Optional, TypeVar

    from github3.issues import Issue
    from github3.pulls import PullRequest

    from ..account import Account
    from ..market import Market

    T = TypeVar("T")


def unauth_login() -> GitHub:
    """Return an unauthorized login to GitHub."""
    return GitHub()


def auth_login(account: Account) -> GitHub:
    """Translate our account objects into their account fields."""
    return login(username=account.GithubUsername, token=account.GithubToken)


@define(slots=False)
class GitHubIssueMixin:
    """Mixin class to represent a GitHub issue."""

    owner: str
    repo: str
    number: int

    def f_generic(self, account: Account, func: Callable[[GitHub, str, str, int], T]) -> T:
        """Return the request method that you feed in, and we provide the lookup info."""
        return func(auth_login(account), self.owner, self.repo, self.number)

    def f_issue(self, account: Account) -> Future[Issue]:
        """Return a Future object which resolves to the relevant Issue object."""
        return parallel(self.f_generic, account, GitHub.issue)

    def f_pr(self, account: Account) -> Future[PullRequest]:
        """Return a Future object which resolves to the relevant PullRequest object."""
        return parallel(self.f_generic, account, GitHub.pull_request)


@define(slots=False)
class ResolveWithPR(DoResolveRule, GitHubIssueMixin):
    """Return True if the specified PR was merged in the past."""

    @require_env(EnvironmentVariable.GithubAccessToken, EnvironmentVariable.GithubUsername)
    def _value(self, market: Market, account: Account) -> bool:
        """Return True if the issue is closed or the PR is merged, otherwise False."""
        f_issue = self.f_issue(account)
        f_pr = self.f_pr(account)
        issue = f_issue.result()
        if issue.state != 'open':
            return True
        pr = f_pr.result()
        return pr is not None and pr.merged

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"

    def _explain_specific(self, market: Market, account: Account, indent: int = 0, sig_figs: int = 4) -> str:
        f_issue = self.f_issue(account)
        f_pr = self.f_pr(account)

        ret = f"{'  ' * indent}- If either of the conditions below are True (-> {self.value(market, account)})\n"
        indent += 1
        issue = f_issue.result()
        ret += f"{'  ' * indent}- If the state of the pull request is not open (-> {issue.state})\n"
        pr = f_pr.result()
        ret += f"{'  ' * indent}- If the pull request is merged (-> {pr is not None and pr.merged})\n"
        return ret


@define(slots=False)
class ResolveToPR(ResolutionValueRule, GitHubIssueMixin):
    """Resolve to True if the PR is merged, otherwise False."""

    def _value(self, market: Market, account: Account) -> bool:
        pr = self.f_pr(account).result()
        return pr is not None and pr.merged

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- Resolves based on GitHub PR {self.owner}/{self.repo}#{self.number}\n"
        indent += 1
        ret += f"{'  ' * indent}- If the PR is merged, resolve to YES.\n"
        ret += f"{'  ' * indent}- Otherwise, resolve to NO.\n"
        return ret

    def _explain_specific(self, market: Market, account: Account, indent: int = 0, sig_figs: int = 4) -> str:
        pr = self.f_pr(account).result()
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

    def _value(self, market: Market, account: Account) -> float:
        pr = self.f_pr(account).result()
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

    def _explain_specific(self, market: Market, account: Account, indent: int = 0, sig_figs: int = 4) -> str:
        pr = self.f_pr(account).result()
        if pr is None:
            merge_time = None
        else:
            merge_time = pr.merged_at
        return (f"{'  ' * indent}- How long after {self.start} was the pull request is merged? (-> "
                f"{merge_time or 'Not yet merged'} -> {self.value(market, account)})\n")
