"""Stub module which helps to manage caching and the launch of parallel network requests."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from os import getenv
from typing import TYPE_CHECKING, TypeVar

import requests_cache

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable

T = TypeVar("T")

CACHE = not getenv("ManifoldMarketManager_NO_CACHE")
if CACHE:
    requests_cache.install_cache(expire_after=360, allowable_methods=('GET', ))
    executor = ThreadPoolExecutor(thread_name_prefix="ManifoldMarketManagerWorker_")
else:
    class Deferred(Future[T]):
        """Dummy future class for use in testing."""

        def __init__(self, func: Callable[[...], T], *args: Any, **kwargs: Any) -> None:
            """Store func and arguments."""
            self.deferred_func = func
            self.args = args
            self.kwargs = kwargs
            super().__init__()

        def result(self, *args: Any, **kwargs: Any) -> T:
            """Execute the deferred function and return its value."""
            self.set_result(self.deferred_func(*self.args, **self.kwargs))
            return super().result(*args, **kwargs)


def parallel(func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
    """Launch a task in parallel UNLESS the ManifoldMarketManager_NO_CACHE environment variable is set.

    I need to be able to disable the cache/parallel launching or VCR doesn't work on testing.
    """
    if CACHE:
        def wrapped() -> T:
            return func(*args, **kwargs)

        return executor.submit(wrapped)
    return Deferred(func, *args, **kwargs)
