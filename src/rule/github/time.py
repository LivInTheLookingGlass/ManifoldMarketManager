from dataclasses import dataclass

from . import get_issue
from .. import DoResolveRule
from ...market import Market


@dataclass
class ResolveWithPR(DoResolveRule):
    """Return True if the specified PR was merged in the past."""

    owner: str
    repo: str
    number: int

    def value(self, market: Market) -> bool:
        json = get_issue(self.owner, self.repo, self.number)
        return (
            "pull_request" in json and (
                (json["pull_request"].get("merged_at") is not None) or (json["state"] != "open")
            )
        )

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"
