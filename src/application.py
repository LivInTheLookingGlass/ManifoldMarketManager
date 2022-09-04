from asyncio import get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from logging import getLogger
from pathlib import Path
from os import getenv
from sqlite3 import connect, PARSE_COLNAMES, PARSE_DECLTYPES
from typing import cast

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

from src import market, require_env

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
