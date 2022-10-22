"""Contains functions which are needed to run the runner script, but nowhere else."""

from __future__ import annotations

from asyncio import get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging import getLogger
from os import getenv
from pathlib import Path
from sqlite3 import PARSE_COLNAMES, PARSE_DECLTYPES, connect
from traceback import format_exc
from typing import TYPE_CHECKING, cast

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

from src import market, require_env
from src.consts import EnvironmentVariable, MarketStatus, Response

if TYPE_CHECKING:  # pragma: no cover
    from sqlite3 import Connection

    from telegram import Update
    from telegram.ext import ContextTypes

    from src import Market

logger = getLogger(__name__)


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
def main(refresh: bool = False, console_only: bool = False) -> None:
    """Go through watched markets and act on rules (resolve, trade, etc)."""
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
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
            msg = f'  - [{"x" if check else " "}] Is elligible to resolve (to {mkt.resolve_to()})?'
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
