from os import getenv

import requests

from ...util import require_env


# curl \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: token <TOKEN>" \
#   https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER

@require_env("GithubAPIKey")
def get_issue(owner: str, repo: str, number: int):
    return requests.get(
        url=f"https://api.github.com/repos/{owner}/{repo}/issues/{number}",
        headers={"Accept": "application/vnd.github+json", "Authorization": getenv('GithubAPIKey')}
    ).json()