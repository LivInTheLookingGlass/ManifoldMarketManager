from dataclasses import dataclass
from os import getenv

from github3 import login

from .. import DoResolveRule
from ...market import Market
from ...util import require_env


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

    @require_env("GithubAPIKey")
    def value(self, market: Market) -> bool:
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        pr = issue.pull_request()
        return issue.state != 'open' or (pr is not None and pr.merged)

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"

    def explain_specific(self, market: Market, indent=0) -> str:
        ret = f"{'  ' * indent}- If either of the conditions below are True (-> {self.value(market)})\n"
        indent += 1
        issue = login(token=getenv('GithubAPIKey')).issue(self.owner, self.repo, self.number)
        ret += f"{'  ' * indent}- If the state of the pull request is not open (-> {issue.state})\n"
        pr = issue.pull_request()
        ret += f"{'  ' * indent}- If the pull request is merged (-> {pr is not None and pr.merged})\n"
        return ret
