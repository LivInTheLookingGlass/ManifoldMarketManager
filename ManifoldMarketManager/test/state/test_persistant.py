"""Test methods of storing persistant state."""

from __future__ import annotations

from os import environ
from typing import TYPE_CHECKING

from pytest import raises

from ...consts import EnvironmentVariable
from ...state.persistant import register_db

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable, TypeVar

    T = TypeVar("T")


def _db_name_wrapper(name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def wrapper(func: Callable[..., T]) -> Callable[..., T]:
        def wrapped(*args: Any, **kwargs: Any) -> T:
            orig = environ.get(EnvironmentVariable.DBName, None)
            environ[EnvironmentVariable.DBName] = name
            try:
                return func(*args, **kwargs)
            finally:
                if orig is None:
                    del environ[EnvironmentVariable.DBName]
                else:
                    environ[EnvironmentVariable.DBName] = orig

        return wrapped

    return wrapper


@_db_name_wrapper(":memory:")
def test_register_db() -> None:
    """Ensure that register_db creates the correct table configurations."""
    conn = register_db()
    # test accounts

    # test markets
    conn.execute('INSERT INTO markets VALUES (1, NULL, 3, NULL, NULL)')
    with raises(Exception):
        conn.execute('INSERT INTO markets VALUES (1, NULL, 3, NULL, NULL)')
    conn.execute('INSERT INTO markets VALUES (2, NULL, 3, NULL, NULL)')

    # test pending
    # test scanners
