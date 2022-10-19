from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from os import getenv
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import TYPE_CHECKING

from vcr import VCR

if TYPE_CHECKING:  # pragma: no cover
    from concurrent.futures import Future
    from typing import Callable, TypeVar

    T = TypeVar("T")

temp_dir = TemporaryDirectory()
vcr = VCR(
    cassette_library_dir=temp_dir.name,
    record_mode="new_episodes",
    match_on=["uri", "query", "headers"],
    filter_headers=["authorization"],
    decode_compressed_response=True
)
executor = ThreadPoolExecutor(thread_name_prefix="ManifoldMarketManagerWorker_")
CACHE = not getenv("ManifoldMarketManager_NO_CACHE")


def cleanup() -> None:
    for f in Path(temp_dir.name).iterdir():
        if f.stat().st_atime + 30 < time():
            f.unlink()


def parallel(func: Callable[..., T], *args, **kwargs) -> Future[T]:
    def wrapped() -> T:
        return func(*args, **kwargs)

    if CACHE:
        wrapped = vcr.use_cassette(wrapped)
    executor.submit(cleanup)
    return executor.submit(wrapped)
