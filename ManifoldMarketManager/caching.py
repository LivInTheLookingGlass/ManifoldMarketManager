"""Stub module which helps to manage caching and the launch of parallel network requests."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from os import getenv
from sys import version_info
from typing import TYPE_CHECKING, Generic, TypeVar, cast

import requests_cache

from .consts import EnvironmentVariable

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable, Optional

T = TypeVar("T")

CACHE = not getenv(EnvironmentVariable.NO_CACHE)
if CACHE:
    requests_cache.install_cache(expire_after=360, allowable_methods=('GET', ))
    executor = ThreadPoolExecutor(thread_name_prefix="ManifoldMarketManagerWorker_")
else:
    if version_info >= (3, 9):  # I hate this
        _Future = Future
    else:
        class _Future(Future, Generic[T]):  # type: ignore
            def result(self, timeout: Optional[float] = None) -> T:
                return cast(T, super().result(timeout))

    class Deferred(_Future[T]):
        """Dummy future class for use in testing."""

        def __init__(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> None:
            """Store func and arguments."""
            self.deferred_func = func
            self.args = args
            self.kwargs = kwargs
            super().__init__()

        def result(self, timeout: Optional[float] = None) -> T:
            """Execute the deferred function and return its value."""
            self.set_result(self.deferred_func(*self.args, **self.kwargs))
            return super().result(timeout)


def parallel(func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
    """Launch a task in parallel UNLESS the ManifoldMarketManager_NO_CACHE environment variable is set.

    I need to be able to disable the cache/parallel launching or VCR doesn't work on testing.
    """
    if CACHE:
        def wrapped() -> T:
            return func(*args, **kwargs)

        return executor.submit(wrapped)
    return Deferred(func, *args, **kwargs)
