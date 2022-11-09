"""Contains functions which are needed to run the runner script, but nowhere else."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from asyncio import get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import count
from logging import getLogger
from os import getenv
from pathlib import Path
from sqlite3 import PARSE_COLNAMES, PARSE_DECLTYPES, connect
from time import sleep
from traceback import format_exc
from typing import TYPE_CHECKING, Tuple, cast

from telegram import __version__ as TG_VER

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler

from . import market, require_env
from .consts import AVAILABLE_SCANNERS, EnvironmentVariable, MarketStatus, Response
from .state.persistant import select_markets, update_market

if TYPE_CHECKING:  # pragma: no cover
    from sqlite3 import Connection
    from typing import Any

    from telegram import Update
    from telegram.ext import ContextTypes

    from . import Market

logger = getLogger(__name__)


def parse_args(*args: Any, **kwargs: Any) -> Namespace:
    """Parse arguments for the CLI."""
    main_parser = ArgumentParser()
    main_parser.add_argument('--no-logging', action='store_false', dest='logging', default=True)
    main_parser.add_argument('-v', '--verbose', action='count', default=0)
    main_parser.add_argument('--just-parse', action='store_true', default=False)

    subparsers = main_parser.add_subparsers()

    import_parser = subparsers.add_parser('import')
    import_parser.add_argument('account', action='store', type=str)
    import_parser.add_argument('file', action='store', type=str, nargs='?')
    import_parser.add_argument('--interactive', action='store_true')
    group = import_parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--yaml', action='store_true')
    group.add_argument('--json', action='store_true')
    group.add_argument('--repl', action='store_true')
    import_parser.set_defaults(func=import_command)
    # TODO: add templates here

    quick_import_parser = subparsers.add_parser('quick-import')
    quick_import_parser.add_argument('account', action='store', type=str)
    quick_import_parser.add_argument(
        '--resolve-when', nargs=2, action='append',
        help="Should be a qualified rule name, followed by a JSON string of its initializers"
    )
    quick_import_parser.add_argument(
        '--resolve-to', nargs=2, action='append', required=True,
        help="Should be a qualified rule name, followed by a JSON string of its initializers"
    )
    quick_import_parser.add_argument('-n', '--notes', type=str, action='store', default='')
    group = quick_import_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--url', action='store', type=str)
    group.add_argument('-s', '--slug', action='store', type=str)
    group.add_argument('-i', '--id', dest='id_', action='store', type=str)
    quick_import_parser.add_argument('-c', '--check-rate', action='store', dest='rate', help='Check rate in hours')

    quick_import_parser.add_argument('-rnd', '--round', dest='round_', action='store_true')
    quick_import_parser.add_argument('-cur', '--current', action='store_true')
    quick_import_parser.add_argument(
        '-rd', '--rel-date', action='store', dest='rel_date',
        help='Please give as "year/month/day" or "year-month-day". Used in: poll, git PR'
    )

    quick_import_parser.add_argument(
        '-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner/repo/num"'
    )
    quick_import_parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

    quick_import_parser.add_argument('-rs', '--random-seed', action='store')
    quick_import_parser.add_argument('-rr', '--random-rounds', action='store', type=int, default=1)
    quick_import_parser.add_argument('-ri', '--random-index', action='store_true')
    quick_import_parser.add_argument('-is', '--index-size', action='store', type=int)
    quick_import_parser.set_defaults(func=quick_create_command)

    # must finish import_parser first
    create_parser = subparsers.add_parser('create', parents=[import_parser], add_help=False)
    create_parser.add_argument('--queue-if-no-funds', action='store_true')
    create_parser.add_argument('--queue', action='store_true')
    create_parser.set_defaults(func=create_command)

    quick_create_parser = subparsers.add_parser('quick-create')
    quick_create_parser.add_argument(
        'type', type=str, choices=["BINARY", "PSEUDO_NUMERIC", "FREE_RESPONSE", "MULTIPLE_CHOICE"]
    )
    quick_create_parser.add_argument('account', action='store', type=str)
    quick_create_parser.add_argument('close-on', action='store', type=str)
    quick_create_parser.add_argument(
        '--resolve-when', nargs=2, action='append',
        help="Should be a qualified rule name, followed by a JSON string of its initializers"
    )
    quick_create_parser.add_argument(
        '--resolve-to', nargs=2, action='append', required=True,
        help="Should be a qualified rule name, followed by a JSON string of its initializers"
    )
    quick_create_parser.add_argument('-n', '--notes', type=str, action='store', default='')
    quick_create_parser.set_defaults(func=quick_create_command)

    scan_parser = subparsers.add_parser('scan')
    scan_parser.add_argument('--disable-all', action='store_false', dest='all_scanners', default=True)
    for scanner in AVAILABLE_SCANNERS:
        scan_parser.add_argument(
            f'--enable-{scanner.replace(".", "-")}', dest='scanners', action='append_const', const=scanner
        )
    scan_parser.set_defaults(func=scan_command)

    run_parser = subparsers.add_parser('run')
    run_parser.add_argument('--enable-all-scanners', action='store_true', dest='all_scanners', default=False)
    for scanner in AVAILABLE_SCANNERS:
        run_parser.add_argument(
            f'--enable-{scanner.replace(".", "-")}', dest='scanners', action='append_const', const=scanner
        )
    run_parser.add_argument(
        '-r', '--refresh', action='store_true',
        help="Ignore time last checked and look at all markets immediately"
    )
    run_parser.add_argument('-c', '--console-only', action='store_true')
    run_parser.set_defaults(func=run_command)

    loop_parser = subparsers.add_parser('loop', parents=[run_parser], add_help=False)
    loop_parser.add_argument(
        '-p', '--period', action='store', type=float, help='how long to wait between loops, in minutes'
    )
    loop_parser.add_argument(
        '-t', '--times', action='store', type=float, default=float('inf'),
        help='how many times to loop (default infinity)'
    )
    loop_parser.set_defaults(func=loop_command)

    edit_parser = subparsers.add_parser('edit')
    edit_parser.add_argument('ids', nargs='+', type=int)
    edit_parser.set_defaults(func=edit_command)

    remove_parser = subparsers.add_parser('remove')
    remove_parser.add_argument('ids', nargs='+', type=int)
    remove_parser.add_argument('--assume-yes', '-y', action='store_true')
    remove_parser.set_defaults(func=remove_command)

    list_parser = subparsers.add_parser('list')
    list_parser.add_argument('--stats', action='store_true')
    list_parser.add_argument('--sig-figs', action='store', type=int, default=4)
    list_parser.set_defaults(func=list_command)

    parsed: Namespace = main_parser.parse_args(*args, **kwargs)

    if hasattr(parsed, 'all_scanners') and parsed.all_scanners:
        parsed.scanners = AVAILABLE_SCANNERS

    return parsed


def _print_uncaught_args(kwargs: dict[str, Any]) -> None:
    if getenv("DEBUG") and kwargs:
        print("Unrecognized arguments:")
        print("\n".join(f'{key}: {value}' for key, value in kwargs.items()))


def import_command(**kwargs: Any) -> int:
    """Import markets from a file without creating any."""
    _print_uncaught_args(kwargs)
    return -1


def quick_import_command(
    url: str | None = None,
    slug: str | None = None,
    id_: str | None = None,
    rel_date: str | None = None,
    random_index: bool = False,
    random_seed: bool = False,
    random_rounds: int = 1,
    round_: bool = False,
    current: bool = False,
    index_size: int | None = None,
    pr_slug: str | None = None,
    pr_bin: bool = False,
    **kwargs: Any
) -> int:
    """Import a single market using the old-style arguments."""
    _print_uncaught_args(kwargs)
    if url:
        mkt = Market.from_url(url)
    elif slug:
        mkt = Market.from_slug(slug)
    else:
        mkt = Market.from_id(cast(str, id_))

    if rel_date:
        sections = rel_date.split('/')
        if len(sections) == 1:
            sections = rel_date.split('-')
        try:
            date: None | tuple[int, int, int] = tuple(int(x) for x in sections)  # type: ignore[assignment]
        except ValueError:
            raise
    else:
        date = None

    if random_index:
        from .rule.generic import ResolveRandomIndex
        mkt.resolve_to_rules.append(
            ResolveRandomIndex(random_seed, size=index_size, rounds=random_rounds)
        )

    if round_:
        from .rule.manifold.this import RoundValueRule
        mkt.resolve_to_rules.append(RoundValueRule())  # type: ignore
    if current:
        from .rule.manifold.this import CurrentValueRule
        mkt.resolve_to_rules.append(CurrentValueRule())

    if pr_slug:
        from .rule.github import ResolveToPR, ResolveToPRDelta, ResolveWithPR
        pr_: list[str | int] = list(pr_slug.split('/'))
        pr_[-1] = int(pr_[-1])
        pr = cast(Tuple[str, str, int], tuple(pr_))
        mkt.do_resolve_rules.append(ResolveWithPR(*pr))
        if date:
            mkt.resolve_to_rules.append(ResolveToPRDelta(*pr, datetime(*date)))
        elif pr_bin:
            mkt.resolve_to_rules.append(ResolveToPR(*pr))
        else:
            raise ValueError("No resolve rule provided")

    if not mkt.do_resolve_rules:
        if not date:
            from .rule.manifold.this import ThisMarketClosed
            mkt.do_resolve_rules.append(ThisMarketClosed())
        else:
            from .rule.generic import ResolveAtTime
            mkt.do_resolve_rules.append(ResolveAtTime(datetime(*date)))

    with register_db() as conn:
        idx = max(((0, ), *conn.execute("SELECT id FROM markets;")))[0] + 1
        conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
        conn.commit()

        msg = f"Successfully added as ID {idx}!"
        print(msg)
        logger.info(msg)
    return 0


def create_command(**kwargs: Any) -> int:
    """Create markets from a file, then import them."""
    _print_uncaught_args(kwargs)
    return -1


def quick_create_command(**kwargs: Any) -> int:
    """Quickly create a single market without need for a file, then import it."""
    _print_uncaught_args(kwargs)
    return -1


def scan_command(**kwargs: Any) -> int:
    """Scan services for markets to create."""
    _print_uncaught_args(kwargs)
    return -1


def run_command(
    refresh: bool = False,
    console_only: bool = False,
    scanners: list[str] = None,  # type: ignore[assignment]
    **kwargs: Any
) -> int:
    """Go through our markets and take actions if needed."""
    _print_uncaught_args(kwargs)
    return main(refresh, console_only) or 0


def loop_command(
    period: float = 5,
    times: float = 5,
    **kwargs: Any
) -> int:
    """Run this service multiple times."""
    # TODO: turn this into an event queue instead
    for i in count():
        if i > times:
            break
        run_command(**kwargs)
        sleep(period * 60)
    return 0


def edit_command(**kwargs: Any) -> int:
    """Edit a market from a temporary file or repl."""
    _print_uncaught_args(kwargs)
    return -1


def remove_command(
    ids: list[int],
    assume_yes: bool = False,
    **kwargs: Any
) -> int:
    """Remove markets from the database."""
    _print_uncaught_args(kwargs)
    for id_ in ids:
        with register_db() as conn:
            try:
                ((mkt, ), ) = conn.execute(
                    "SELECT market FROM markets WHERE id = ?;",
                    (id_, )
                )
            except ValueError:
                print(f"No market with id {id_} exists.")
                return 1
            question = f'Are you sure you want to remove {id_}: "{mkt.market.question}" (y/N)?'
            if (assume_yes or input(question).lower().startswith('y')):
                conn.execute(
                    "DELETE FROM markets WHERE id = ?;",
                    (id_, )
                )
                conn.commit()
                logger.info(f"{id_} removed from db")
    return 0


def list_command(
    stats: bool = False,
    verbose: int = 0,
    sig_figs: int = 4,
    **kwargs: Any
) -> int:
    """List markets from the database in varying verbosity."""
    _print_uncaught_args(kwargs)
    with register_db() as conn:
        id_: int
        mkt: Market
        check_rate: float
        last_check: datetime | None
        for id_, mkt, check_rate, last_check in conn.execute("SELECT * FROM markets"):
            info = f"Market ID: {id_} (internal), {mkt.id} (manifold)\n"
            hours = int(check_rate)
            minutes = (check_rate - hours) // 60
            seconds = ((check_rate - hours) / 60 - minutes) // 60
            info += f"Checks every {hours}:{minutes}:{seconds}\tLast checked: {last_check}\n"
            info += f"Question: {mkt.market.question}\n"
            if verbose:
                info += mkt.explain_abstract(sig_figs=sig_figs) + "\n"

            print(info)
    return 0


@dataclass
class State:
    """Keeps track of global state for while the Telegram Bot is running."""

    application: Application = None  # type: ignore
    last_response: Response = Response.NO_ACTION
    last_text: str = ""


state = State()
keyboard1 = [
    [
        InlineKeyboardButton("Do Nothing", callback_data=Response.NO_ACTION),
        InlineKeyboardButton("Resolve to Default", callback_data=Response.USE_DEFAULT),
    ],
    [InlineKeyboardButton("Cancel Market", callback_data=Response.CANCEL)],
]
keyboard2 = [
    [
        InlineKeyboardButton("Yes", callback_data="YES"),
        InlineKeyboardButton("No", callback_data="NO"),
    ],
]


@require_env(EnvironmentVariable.DBName)
def register_db() -> Connection:
    """Get a connection to the appropriate database for this bot."""
    name = getenv("DBName")
    if name is None:
        raise EnvironmentError()
    do_initialize = not Path(name).exists()
    conn = connect(name, detect_types=PARSE_COLNAMES | PARSE_DECLTYPES)
    if do_initialize:
        conn.execute("CREATE TABLE markets "
                     "(id INTEGER, market Market, check_rate REAL, last_checked TIMESTAMP);")
        conn.commit()
    logger.info("Database up and initialized.")
    return conn


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parse the CallbackQuery and update the message text."""
    logger.info("Got into the buttons handler")
    query = update.callback_query
    if query is None or query.data is None:
        raise ValueError()

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    logger.info("Got a response from Telegram (%r)", query.data)
    if query.data in ("YES", "NO"):
        state.last_text += "\n" + query.data
        await query.edit_message_text(text=state.last_text)
        if query.data != "YES":
            logger.info("Was not told yes. Backing out to ask again")
            reply_markup = InlineKeyboardMarkup(keyboard1)
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        else:
            logger.info("Confirmation received, shutting dowm Telegram subsystem")
            get_event_loop().stop()  # lets telegram bot know it can stop
    else:
        state.last_response = Response(int(query.data))
        logger.info("This corresponds to %r", state.last_response)
        reply_markup = InlineKeyboardMarkup(keyboard2)
        state.last_text += f"\nSelected option: {state.last_response.name}. Are you sure?"
        await query.edit_message_text(text=state.last_text)
        await query.edit_message_reply_markup(reply_markup=reply_markup)


@require_env(EnvironmentVariable.TelegramAPIKey, EnvironmentVariable.TelegramChatID)
def tg_main(text: str) -> Response:
    """Run the bot."""
    async def post_init(self):  # type: ignore
        reply_markup = InlineKeyboardMarkup(keyboard1)
        chat_id = getenv("TelegramChatID")
        if chat_id is None:
            raise EnvironmentError()
        await self.bot.send_message(text=text, reply_markup=reply_markup, chat_id=int(chat_id))

    application = Application.builder().token(cast(str, getenv("TelegramAPIKey"))).post_init(post_init).build()
    application.add_handler(CallbackQueryHandler(buttons))

    state.application = application
    state.last_text = text

    set_event_loop(new_event_loop())
    application.run_polling()
    return state.last_response


def watch_reply(conn: Connection, id_: int, mkt: Market, console_only: bool = False) -> None:
    """Watch for a reply from the bot manager in order to check the bot's work."""
    text = (f"Hey, we need to resolve {id_} to {mkt.resolve_to()}. It currently has a value of {mkt.current_answer()}."
            f"This market is called: {mkt.market.question}\n\n")
    text += mkt.explain_abstract()
    try:
        text += "\n\n" + mkt.explain_specific()
    except Exception:
        print(format_exc())
        logger.exception("Unable to explain a market's resolution automatically")
    if not console_only:
        response = tg_main(text)
    else:
        if input(text + " Use this default value? (y/N) ").lower().startswith("y"):
            response = Response.USE_DEFAULT
        elif input("Cancel the market? (y/N) ").lower().startswith("y"):
            response = Response.CANCEL
        else:
            response = Response.NO_ACTION

    if response == Response.NO_ACTION:
        return
    elif response == Response.USE_DEFAULT:
        resp = mkt.resolve()
    elif response == Response.CANCEL:
        resp = mkt.cancel()
    if mkt.status != MarketStatus.RESOLVED:
        raise RuntimeError(resp)
    conn.execute(
        "DELETE FROM markets WHERE id = ?;",
        (id_, )
    )
    conn.commit()


@require_env(EnvironmentVariable.ManifoldAPIKey, EnvironmentVariable.DBName)
def main(refresh: bool = False, console_only: bool = False) -> int:
    """Go through watched markets and act on rules (resolve, trade, etc)."""
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked, _ in select_markets((), conn):
        msg = f"Currently checking ID {id_}: {mkt.market.question}"
        print(msg)
        logger.info(msg)
        # print(mkt.explain_abstract())
        # print("\n\n" + mkt.explain_specific() + "\n\n")
        check = (refresh or not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)))
        msg = f'  - [{"x" if check else " "}] Should I check?'
        print(msg)
        logger.info(msg)
        if check:
            check = mkt.should_resolve()
            msg = f'  - [{"x" if check else " "}] Is elligible to resolve?'
            print(msg)
            logger.info(msg)
            if check:
                watch_reply(conn, id_, mkt, console_only)

            if mkt.market.isResolved:
                msg = "  - [x] Market resolved, removing from db"
                print(msg)
                logger.info(msg)
                conn.execute(
                    "DELETE FROM markets WHERE id = ?;",
                    (id_, )
                )
                conn.commit()

        conn.execute(
            "UPDATE markets SET last_checked = ?, market = ? WHERE id = ?;",
            (datetime.now(), mkt, id_)
        )
        conn.commit()
    conn.close()
    return 0
