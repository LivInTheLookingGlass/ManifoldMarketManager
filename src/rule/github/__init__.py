from __future__ import annotations

from os import getenv

from github3 import GitHub
from github3 import login as gh_login

from ...util import require_env

__all__ = ('login', 'value', 'time', 'unauth_login')


def unauth_login() -> GitHub:
    """Return an unauthorized login to GitHub."""
    return GitHub()


@require_env('GithubAccessToken', 'GithubUsername')
def login() -> GitHub:
    """Return an authorized login to GitHub."""
    return gh_login(username=getenv('GithubUsername'), token=getenv('GithubAccessToken'))


from . import time, value  # noqa: E402
