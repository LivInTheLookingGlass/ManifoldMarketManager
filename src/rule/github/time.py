from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...util import require_env
from .. import DoResolveRule
from . import login

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ...market import Market


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

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
