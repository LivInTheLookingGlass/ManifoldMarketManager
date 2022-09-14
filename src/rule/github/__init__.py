from os import getenv

from github3 import GitHub, login as gh_login

from ...util import require_env


def unauth_login():
    return GitHub()


@require_env('GithubAccessToken', 'GithubUsername')
def login():
    return gh_login(username=getenv('GithubUsername'), token=getenv('GithubAccessToken'))
