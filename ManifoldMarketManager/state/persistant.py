"""Store state between sessions."""

from __future__ import annotations

from functools import lru_cache
from logging import getLogger
from os import getenv
from pathlib import Path
from sqlite3 import PARSE_COLNAMES, PARSE_DECLTYPES, connect
from typing import TYPE_CHECKING

from ..account import Account
from ..consts import EnvironmentVariable
from ..util import require_env

if TYPE_CHECKING:  # pragma: no cover
    from datetime import datetime
    from sqlite3 import Connection
    from typing import Any, Iterable, Sequence

    from ..market import Market

logger = getLogger(__name__)


@require_env(EnvironmentVariable.DBName)
def register_db() -> Connection:
    """Get a connection to the appropriate database for this bot."""
    name = getenv("DBName")
    if name is None:
        raise EnvironmentError()
    do_initialize = not Path(name).exists()
    conn = connect(name, detect_types=PARSE_COLNAMES | PARSE_DECLTYPES)
    if do_initialize:
        conn.execute(
            "CREATE TABLE accounts "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, manidfold_id TEXT NOT NULL, username TEXT NOT NULL, "
            "raw_account BLOB, is_encrypted BOOLEAN, account Account)"
        )
        conn.execute(
            "CREATE TABLE markets "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, market Market NOT NULL, check_rate REAL NOT NULL, "
            "last_checked TIMESTAMP, account INTEGER REFERENCES \"accounts\" (\"id\") ON DELETE SET NULL)"
        )
        conn.execute(
            "CREATE TABLE pending "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, request ManagerRequest NOT NULL, priority REAL NOT NULL, "
            "account INTEGER REFERENCES \"accounts\" (\"id\") ON DELETE SET NULL)"
        )
        conn.execute(
            "CREATE TABLE scanners "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, scanner EventEmitter NOT NULL, state Namesapce, "
            "check_rate REAL NOT NULL, last_checked TIMESTAMP, "
            "account INTEGER REFERENCES \"accounts\" (\"id\") ON DELETE SET NULL)"
        )
        conn.commit()
    logger.info("Database up and initialized.")
    return conn


def select_markets(keys: Sequence[bytes] = ()) -> Iterable[tuple[int, Market, float, datetime | None, Account | None]]:
    """Attempt to load ALL market objects from the database, with their associated metadata.

    Requires: some number of keys if your market has encrypted accounts associated with it.

    Depends on: select_account()
    """
    key_strs = getenv(EnvironmentVariable.AccountKeys, "").split(",")
    keys = (*keys, *(bytes.fromhex(x) for x in key_strs))
    with register_db() as db:
        row: tuple[int, Market, float, datetime | None, int | None]
        for row in db.execute("SELECT id, market, check_rate, last_checked, account from markets"):
            row_id, market, check_rate, last_checked, account_id = row
            account: Account | None = None
            if account_id is not None:
                for key in keys:
                    _, account = select_account(db_id=account_id, key=key)
                    break
            yield (row_id, market, check_rate, last_checked, account)


@lru_cache
def select_account(
    db_id: int | None = None,
    manifold_id: str | None = None,
    username: str | None = None,
    key: bytes = b''
) -> tuple[int, Account]:
    """Attempt to load and decrypt a SINGLE account object from the database.

    Raises an error if not exactly one is returned or if it cannot be decrypted.
    """
    with register_db() as db:
        query = "from accounts select id, raw_account, account, is_encrypted where "
        params: tuple[Any, ...] = ()
        if db_id:
            query += "ID = ? "
            params += (db_id, )
        if manifold_id:
            if db_id:
                query += ", "
            query += "manifold_id = ? "
            params += (manifold_id, )
        if username:
            if any((db_id, manifold_id)):
                query += ", "
            query += "username = ? "
            params += (username, )
        ((id_, raw_account, account, is_encrypted), )  = db.execute(query, params)
        if is_encrypted:
            account = Account.from_bytes(raw_account, key)
        return (id_, account)
