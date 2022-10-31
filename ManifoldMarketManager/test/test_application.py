from __future__ import annotations

from os import environ

from ..application import register_db
from ..consts import EnvironmentVariable


def test_register_db() -> None:
    orig = environ.get(EnvironmentVariable.DBName, None)
    environ[EnvironmentVariable.DBName] = ':memory:'
    try:
        conn = register_db()
        conn.execute('INSERT INTO markets VALUES (1, NULL, 3, NULL)')
    finally:
        if orig is None:
            del environ[EnvironmentVariable.DBName]
        else:
            environ[EnvironmentVariable.DBName] = orig
