"""Allow users to request confirmation via Telegram."""

from __future__ import annotations

from asyncio import get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass
from logging import getLogger
from os import getenv
from typing import TYPE_CHECKING, cast

from telegram import __version__ as TG_VER

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, "", 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler

if TYPE_CHECKING:  # pragma: no cover
    from telegram import Update
    from telegram.ext import ContextTypes

    from ..account import Account
    from ..consts import EnvironmentVariable, Response

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


def tg_main(text: str, account: Account) -> Response:
    """Run the bot."""
    async def post_init(self):  # type: ignore
        reply_markup = InlineKeyboardMarkup(keyboard1)
        if account.TelegramChatID is None:
            raise EnvironmentError()
        await self.bot.send_message(text=text, reply_markup=reply_markup, chat_id=int(account.TelegramChatID))

    application = Application.builder().token(
        cast(str, getenv(EnvironmentVariable.TelegramAPIKey))
    ).post_init(post_init).build()
    application.add_handler(CallbackQueryHandler(buttons))

    state.application = application
    state.last_text = text

    set_event_loop(new_event_loop())
    application.run_polling()
    return state.last_response
