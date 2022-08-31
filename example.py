from argparse import ArgumentParser
from asyncio import get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from logging import basicConfig, getLogger, DEBUG, INFO
from pathlib import Path
from os import getenv
from sqlite3 import connect, PARSE_COLNAMES, PARSE_DECLTYPES
from typing import cast, Optional, Tuple

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

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from src import (market, require_env, rule)

# Enable logging
basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=(INFO if not getenv("DEBUG") else DEBUG),
    filename=getenv("LogFile"),
)
logger = getLogger(__name__)


class Response(IntEnum):
    """Possible responses from the Telegram Bot, other than YES or NO."""

    NO_ACTION = 1
    USE_DEFAULT = 2
    CANCEL = 3


@dataclass
class State:
    """Keeps track of global state for while the Telegram Bot is running."""

    application: Application = None  # type: ignore[assignment]
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


@require_env("DBName")
def register_db():
    """Get a connection to the appropriate database for this bot."""
    do_initialize = not Path(getenv("DBName")).exists()
    conn = connect(getenv("DBName"), detect_types=PARSE_COLNAMES | PARSE_DECLTYPES)
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


@require_env("TelegramAPIKey", "TelegramChatID")
def tg_main(text) -> Response:
    """Run the bot."""
    async def post_init(self):
        reply_markup = InlineKeyboardMarkup(keyboard1)
        await self.bot.send_message(text=text, reply_markup=reply_markup, chat_id=int(getenv("TelegramChatID")))

    application = Application.builder().token(cast(str, getenv("TelegramAPIKey"))).post_init(post_init).build()
    application.add_handler(CallbackQueryHandler(buttons))

    state.application = application
    state.last_text = text

    set_event_loop(new_event_loop())
    application.run_polling()
    return state.last_response


def watch_reply(conn, id_, mkt, console_only=False):
    """Watch for a reply from the bot manager in order to check the bot's work."""
    text = (f"Hey, we need to resolve {id_} to {mkt.resolve_to()}. It currently has a value of {mkt.current_answer()}."
            f"This market is called: {mkt.market.question}\n\n")
    text += mkt.explain_abstract()
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
    if mkt.status != market.MarketStatus.RESOLVED:
        raise RuntimeError(resp)
    conn.execute(
        "DELETE FROM markets WHERE id = ?;",
        (id_, )
    )
    conn.commit()


@require_env("ManifoldAPIKey", "DBName")
def main(refresh: bool = False, console_only: bool = False):
    """Go through watched markets and act on rules (resolve, trade, etc)."""
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
        print(msg := f"Currently checking ID {id_}: {mkt.market.question}")
        logger.info(msg)
        print(mkt.explain_abstract())
        check = (refresh or not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)))
        print(msg := f'  - [{"x" if check else " "}] Should I check?')
        logger.info(msg)
        if check:
            check = mkt.should_resolve()
            print(msg := f'  - [{"x" if check else " "}] Is elligible to resolve (to {mkt.resolve_to()})?')
            logger.info(msg)
            if check:
                watch_reply(conn, id_, mkt, console_only)

            if mkt.market.isResolved:
                print(msg := "  - [x] Market resolved, removing from db")
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


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-s', '--add-slug', action='store', dest='slug')
    parser.add_argument('-i', '--add-id', action='store', dest='id_')
    parser.add_argument('-u', '--add-url', action='store', dest='url')
    parser.add_argument('-c', '--check-rate', action='store', dest='rate', help='Check rate in hours')

    parser.add_argument('-mi', '--min', action='store',
                        help="Only used for numeric markets, until they add this to the API")
    parser.add_argument('-ma', '--max', action='store',
                        help="Only used for numeric markets, until they add this to the API")
    parser.add_argument('-ls', '--log_scale', action='store_true', dest='isLogScale',
                        help="Only used for numeric markets, until they add this to the API")

    parser.add_argument('-r', '--refresh', action='store_true', dest='refresh',
                        help="Ignore time last checked and look at all markets immediately")

    parser.add_argument('-rm', '--remove-id', action='append', dest='rm_id', default=[],
                        help="Remove a specific market from management. May be repeated.")

    parser.add_argument('-rnd', '--round', action='store_true')
    parser.add_argument('-cur', '--current', action='store_true')
    parser.add_argument('-rd', '--rel-date', action='store', dest='rel_date',
                        help='Please give as "year/month/day" or "year-month-day". Used in: poll, git PR')

    parser.add_argument('-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner/repo/num"')
    parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

    parser.add_argument('-sk', '--skip', action='store_true')
    parser.add_argument('-co', '--console-only', action='store_true')

    parser.add_argument('-rs', '--random-seed', action='store')
    parser.add_argument('-rr', '--random-rounds', action='store', type=int, default=1)
    parser.add_argument('-ri', '--random-index', action='store_true')
    parser.add_argument('-is', '--index-size', action='store', type=int)

    args = parser.parse_args()

    for id_ in args.rm_id:
        conn = register_db()
        ((mkt, ), ) = conn.execute(
            "SELECT market FROM markets WHERE id = ?;",
            (id_, )
        )
        if input(f'Are you sure you want to remove {id_}: "{mkt.market.question}" (y/N)?').lower().startswith('y'):
            conn.execute(
                "DELETE FROM markets WHERE id = ?;",
                (id_, )
            )
            conn.commit()
            logger.info(f"{id_} removed from db")
        conn.close()

    if any((args.slug, args.id_, args.url)):
        if args.url:
            args.slug = args.url.split('/')[-1]

        if args.slug:
            mkt = market.Market.from_slug(args.slug)
        else:
            mkt = market.Market.from_id(args.id)

        if args.rel_date:
            sections = args.rel_date.split('/')
            if len(sections) == 1:
                sections = args.rel_date.split('-')
            try:
                date: Optional[Tuple[int, int, int]] = tuple(int(x) for x in sections)  # type: ignore[assignment]
            except ValueError:
                raise
        else:
            date = None

        if args.random_index:
            mkt.resolve_to_rules.append(
                rule.ResolveRandomIndex(args.random_seed, size=args.index_size, rounds=args.random_rounds)
            )

        if args.round:
            mkt.resolve_to_rules.append(rule.RoundValueRule())
        if args.current:
            mkt.resolve_to_rules.append(rule.CurrentValueRule())

        if args.pr_slug:
            pr_ = list(args.pr_slug.split('/'))
            pr_[-1] = int(pr_[-1])
            pr = cast(Tuple[str, str, int], tuple(pr_))
            mkt.do_resolve_rules.append(rule.ResolveWithPR(*pr))
            if date:
                mkt.resolve_to_rules.append(rule.ResolveToPRDelta(*pr, datetime(*date)))
            elif args.pr_bin:
                mkt.resolve_to_rules.append(rule.ResolveToPR(*pr))
            else:
                raise ValueError("No resolve rule provided")

        if not mkt.do_resolve_rules:
            if not date:
                raise ValueError("No resolve date provided")
            mkt.do_resolve_rules.append(rule.ResolveAtTime(datetime(*date)))

        conn = register_db()

        idx = max(((0, ), *conn.execute("SELECT id FROM markets;")))[0] + 1
        conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
        conn.commit()

        print(msg := f"Successfully added as ID {idx}!")
        logger.info(msg)
        conn.close()

    if not args.skip:
        main(args.refresh, args.console_only)
