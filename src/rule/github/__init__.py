from os import getenv

from github3 import GitHub
from github3 import login as gh_login

from ...util import require_env


def unauth_login() -> GitHub:
    return GitHub()


@require_env('GithubAccessToken', 'GithubUsername')
def login() -> GitHub:
    return gh_login(username=getenv('GithubUsername'), token=getenv('GithubAccessToken'))
