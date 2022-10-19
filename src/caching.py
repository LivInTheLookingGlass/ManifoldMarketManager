"""Stub module which helps to manage caching and the launch of parallel network requests."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from os import getenv
from typing import TYPE_CHECKING

import requests_cache

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable, TypeVar

    T = TypeVar("T")

CACHE = not getenv("ManifoldMarketManager_NO_CACHE")
if CACHE:
    requests_cache.install_cache(expire_after=360, allowable_methods=('GET', ))
    executor = ThreadPoolExecutor(thread_name_prefix="ManifoldMarketManagerWorker_")


def parallel(func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
    """Launch a task in parallel UNLESS the ManifoldMarketManager_NO_CACHE environment variable is set.

    I need to be able to disable the cache/parallel launching or VCR doesn't work on testing.
    """
    if CACHE:
        def wrapped() -> T:
            return func(*args, **kwargs)

        return executor.submit(wrapped)
    ret: Future[T] = Future()
    ret.set_result(func(*args, **kwargs))
    return ret
