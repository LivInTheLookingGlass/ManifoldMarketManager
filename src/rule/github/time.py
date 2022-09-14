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
            (json["state"] != "open") or (
                ("pull_request" in json) and (json["pull_request"].get("merged_at") is not None)
            )
        )

    def explain_abstract(self, indent=0, **kwargs) -> str:
        return f"{'  ' * indent}- If the GitHub PR {self.owner}/{self.repo}#{self.number} was merged in the past.\n"

    def explain_specific(self, market: Market, indent=0) -> str:
        ret = f"{'  ' * indent}- If either of the conditions below are True (-> {self.value(market)})\n"
        indent += 1
        json = get_issue(self.owner, self.repo, self.number)
        ret += f"{'  ' * indent}- If the state of the pull request is not open (-> {json['state']})\n"
        merge_time = json.get('pull_request', {}).get('merged_at')
        ret += f"{'  ' * indent}- If the pull request is merged (-> {merge_time} -> {merge_time is not None})\n"
        return ret
