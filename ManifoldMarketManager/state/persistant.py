"""Store state between sessions."""

from __future__ import annotations

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
    from sqlite3 import Connection, Cursor
    from typing import Any, Callable, Iterable, Sequence

    from ..market import Market
    from ..util import T

logger = getLogger(__name__)


def db_wrapper(func: Callable[..., T]) -> Callable[..., T]:
    """Wrap a function so that it automatically gets a reference to the database if one is not provided."""
    def wrapper(*args: Any, db: Connection | None = None, **kwargs: Any) -> T:
        if db is None:
            with register_db() as db:
                return func(*args, db=db, **kwargs)
        return func(*args, db=db, **kwargs)
    return wrapper


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
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, market Market, check_rate REAL NOT NULL, last_checked TIMESTAMP, "
            "account INTEGER REFERENCES \"accounts\" (\"id\") ON DELETE SET NULL)"
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


@db_wrapper
def remove_markets(
    *row_id: int,
    db: Connection = None  # type: ignore[assignment]
) -> None:
    """Attempt to delete a market in the database."""
    assert db is not None
    db.execute(f"DELETE FROM markets WHERE {' OR '.join(['id = ?'] * len(row_id))}", row_id)


@db_wrapper
def find_account(
    account: Account,
    db: Connection = None  # type: ignore[assignment]
) -> int:
    """Find the ID of an account, if it's registered."""
    id_, _ = select_account(username=account.ManifoldUsername, key=account.key)
    return id_


@db_wrapper
def update_market(
    row_id: int,
    market: Market | None = None,
    check_rate: float | None = None,
    last_checked: datetime | None = None,
    account_id: int | None = None,
    account: Account | None = None,
    db: Connection = None  # type: ignore[assignment]
) -> None:
    """Attempt to update a market in the database."""
    assert db is not None
    params: tuple[Any, ...] = ()
    q_additions = []
    if market is not None:
        q_additions.append("market=?")
        params += (market, )
    if check_rate is not None:
        q_additions.append("check_rate=?")
        params += (check_rate, )
    if last_checked is not None:
        q_additions.append("last_checked=?")
        params += (last_checked, )
    if account_id is not None:
        q_additions.append("account=?")
        params += (account_id, )
    elif account is not None:
        q_additions.append("account=?")
        account_id = find_account(account, db)
        params += (account_id, )
    if not params:
        raise ValueError("you need to actually update something")
    query = f"UPDATE markets SET {', '.join(q_additions)} WHERE id=?"
    params += (row_id, )
    db.execute(query, params)


@db_wrapper
def select_markets(
    keys: Sequence[bytes] = (),
    db: Connection = None  # type: ignore[assignment]
) -> Iterable[tuple[int, Market, float, datetime | None, Account | None]]:
    """Attempt to load ALL market objects from the database, with their associated metadata.

    Requires: some number of keys if your market has encrypted accounts associated with it.

    Depends on: select_account()
    """
    assert db is not None
    key_strs = getenv(EnvironmentVariable.AccountKeys, "").split(",")
    keys = (*keys, *(bytes.fromhex(x) for x in key_strs))
    row: tuple[int, Market, float, datetime | None, int | None]
    for row in db.execute("SELECT * from markets"):
        row_id, market, check_rate, last_checked, *extra = row
        account_id: int | None
        if extra:
            (account_id, ) = extra
        else:
            account_id = None
        account: Account | None = None
        if account_id is not None:
            for key in keys:
                _, account = select_account(db_id=account_id, key=key)
                break
        yield (row_id, market, check_rate, last_checked, account)


@db_wrapper
def select_account(
    db_id: int | None = None,
    manifold_id: str | None = None,
    username: str | None = None,
    key: bytes = b'',
    db: Connection = None  # type: ignore[assignment]
) -> tuple[int, Account]:
    """Attempt to load and decrypt a SINGLE account object from the database.

    Raises an error if not exactly one is returned or if it cannot be decrypted.
    """
    assert db is not None
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
    ((id_, raw_account, account, is_encrypted), ) = db.execute(query, params)
    if is_encrypted:
        account = Account.from_bytes(raw_account, key)
    return (id_, account)


class DatabaseNamespace:
    """Reperesent a namespace in the database for use by various rules and plugins.

    This requires you to give a schema and UUID-formatted table name. If your name is not a UUID format, it will error.
    """

    def __init__(self, uuid: str, schema: dict[str, str | type]):
        self.uuid = uuid.replace("-", "_")
        str_schema = ", ".join(f"{name} {type_}" for name, type_ in schema.items())
        self.execute(f"CREATE TABLE {self.uuid} IF NOT EXIST ? ({str_schema})", commit=True)

    def execute(self, query: str, commit: bool = False) -> Cursor:
        """Perform basic sanitization that I don't expect to defeat real effort unless you use this responsibly."""
        if len(self.uuid) == 36 or ';' in query:
            raise ValueError()
        db = register_db()
        ret = db.execute(query)
        if commit:
            db.commit()
        return ret

    def select(
        self,
        names: Sequence[str] = ("*", )
    ) -> Cursor:
        """Select from your database namespace."""
        return self.execute(f"SELECT {', '.join(names)} FROM {self.uuid}")

    def remove(
        self,
        names: Sequence[str] = ("*", )
    ) -> Cursor:
        """Remove from your database namespace."""
        raise NotImplementedError()

    def update(
        self,
        names: Sequence[str] = ("*", )
    ) -> Cursor:
        """Update values in your database namespace."""
        raise NotImplementedError()
