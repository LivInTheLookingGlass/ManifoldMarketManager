from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path
from os import getenv
from signal import raise_signal, SIGINT
from sqlite3 import connect, PARSE_COLNAMES, PARSE_DECLTYPES
from typing import cast, Optional, Tuple

import logging

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

from src import (market, rule)


class Response(IntEnum):
    NO_ACTION = 1
    USE_DEFAULT = 2


@dataclass
class State:
    application: Application = None  # type: ignore
    last_response: Response = Response.NO_ACTION
    last_text: str = ""


state = State()
keyboard1 = [
    [
        InlineKeyboardButton("Do Nothing", callback_data="1"),
        InlineKeyboardButton("Resolve to Default", callback_data="2"),
    ],
    [InlineKeyboardButton("Cancel Market", callback_data="3")],
]
keyboard2 = [
    [
        InlineKeyboardButton("Yes", callback_data="YES"),
        InlineKeyboardButton("No", callback_data="NO"),
    ],
]


# Enable logging
logging.basicConfig(

    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def require_env(func):
    def foo(*args, **kwargs):
        if not all(getenv(x) for x in ("ManifoldAPIKey", "GithubAPIKey", "DBName", "TelegramAPIKey", "TelegramChatID")):
            raise EnvironmentError("Please call 'source env.sh' first")
        return func(*args, **kwargs)

    return foo


@require_env
def register_db():
    do_initialize = not Path(getenv("DBName")).exists()
    conn = connect(getenv("DBName"), detect_types=PARSE_COLNAMES | PARSE_DECLTYPES)
    if do_initialize:
        conn.execute("CREATE TABLE markets "
                     "(id INTEGER, market Market, check_rate REAL, last_checked TIMESTAMP);")
        conn.commit()
    return conn


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    if query is None or query.data is None:
        raise ValueError()

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    if query.data in ("YES", "NO"):
        state.last_text += "\n" + query.data
        await query.edit_message_text(text=state.last_text)
        if query.data != "YES":
            reply_markup = InlineKeyboardMarkup(keyboard1)
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        else:
            raise_signal(SIGINT)  # lets telegram bot know it can stop
    else:
        state.last_response = Response(int(query.data))
        reply_markup = InlineKeyboardMarkup(keyboard2)
        state.last_text += f"\nSelected option: {state.last_response.name}. Are you sure?"
        await query.edit_message_text(text=state.last_text)
        await query.edit_message_reply_markup(reply_markup=reply_markup)


@require_env
def tg_main(text) -> Response:
    """Run the bot."""
    async def post_init(self):
        reply_markup = InlineKeyboardMarkup(keyboard1)
        await self.bot.send_message(text=text, reply_markup=reply_markup, chat_id=int(getenv("TelegramChatID")))

    application = Application.builder().token(cast(str, getenv("TelegramAPIKey"))).post_init(post_init).build()
    application.add_handler(CallbackQueryHandler(buttons))

    state.application = application
    state.last_text = text

    application.run_polling()
    return state.last_response


def watch_reply(id_, mkt):
    conn = register_db()
    text = f"Hey, we need to resolve {id_} to {mkt.resolve_to()}. It currently has a value of {mkt.current_answer()}."
    response = tg_main(text)
    if response == Response.NO_ACTION:
        return
    elif response == Response.USE_DEFAULT:
        mkt.resolve()
    elif response == Response.CANCEL:
        mkt.cancel()
        conn.execute(
            "DELETE FROM markets WHERE id = ?;",
            (id_, )
        )
        conn.commit()


@require_env
def main(refresh: bool = False):
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
        print(f"Currently checking ID {id_}: {mkt.market.question}")
        check = (refresh or not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)))
        print(f'  - [{"x" if check else " "}] Should I check?')
        if check:
            check = mkt.should_resolve()
            print(f'  - [{"x" if check else " "}] Is elligible to resolve (to {mkt.resolve_to()})?')
            if check:
                watch_reply(id_, mkt)

            if mkt.market.isResolved:
                print("  - [x] Market resolved, removing from db")
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


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-s', '--add-slug', action='store', dest='slug')
    parser.add_argument('-i', '--add-id', action='store', dest='id_')
    parser.add_argument('-u', '--add-url', action='store', dest='url')
    parser.add_argument('-c', '--check-rate', action='store', dest='rate', help='Check rate in hours')

    parser.add_argument('-mi', '--min', action='store', dest='max',
                        help="Only used for numeric markets, until they add this to the API")
    parser.add_argument('-ma', '--max', action='store', dest='min',
                        help="Only used for numeric markets, until they add this to the API")
    parser.add_argument('-ls', '--log_scale', action='store_true', dest='isLogScale',
                        help="Only used for numeric markets, until they add this to the API")

    parser.add_argument('-r', '--refresh', action='store_true', dest='refresh',
                        help="Ignore time last checked and look at all markets immediately")

    parser.add_argument('-rm', '--remove-id', action='append', dest='rm_id', default=[],
                        help="Remove a specific market from management. May be repeated.")

    parser.add_argument('-pl', '--poll', action='store_true', dest='poll')
    parser.add_argument('-rd', '--rel-date', action='store', dest='rel_date',
                        help='Please give as "year/month/day" or "year-month-day". Used in: poll, git PR')

    parser.add_argument('-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner/repo/num"')
    parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

    parser.add_argument('-sk', '--skip', action='store_true')

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

    if any((args.slug, args.id_, args.url)):
        if args.url:
            args.slug = args.url.split('/')[-1]

        if args.slug:
            mkt = market.Market.from_slug(args.slug, min=args.min, max=args.max, isLogScale=args.isLogScale)
        else:
            mkt = market.Market.from_id(args.id, min=args.min, max=args.max, isLogScale=args.isLogScale)
        if mkt.market.outcomeType == "PSEUDO_NUMERIC" and not all((args.min, args.max)):
            raise ValueError("Until Manifold returns these values, record them yourself")

        if args.rel_date:
            sections = args.rel_date.split('/')
            if len(sections) == 1:
                sections = args.rel_date.split('-')
            try:
                year, month, day = tuple(int(x) for x in sections)
            except ValueError:
                raise
            date: Optional[Tuple[int, int, int]] = (year, month, day)
        else:
            date = None

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

        if args.poll:
            if not date:
                raise ValueError("No resolve date provided")
            mkt.do_resolve_rules.append(rule.ResolveAtTime(datetime(*date)))

        if not all(((mkt.resolve_to_rules or args.poll), mkt.do_resolve_rules)):
            raise ValueError("Cannot add unmanaged market")

        conn = register_db()

        idx = max(conn.execute("SELECT id FROM markets;"))[0] + 1
        conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
        conn.commit()

        print(f"Successfully added as ID {idx}!")

    if not args.skip:
        main(args.refresh)
