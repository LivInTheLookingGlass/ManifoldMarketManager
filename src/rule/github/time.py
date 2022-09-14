from dataclasses import dataclass
from os import getenv

import requests

from .. import DoResolveRule
from ...market import Market


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

# curl \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: token <TOKEN>" \
#   https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER

    def value(self, market: Market) -> bool:
        response = requests.get(
            url=f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}",
            headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
        )
        json = response.json()
        return (
            "pull_request" in json and (
                (json["pull_request"].get("merged_at") is not None) or (json["state"] != "open")
            )
        )

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"
