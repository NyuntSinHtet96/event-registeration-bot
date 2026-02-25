from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.keyboards import main_menu_keyboard


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    await update.message.reply_text(
        "Welcome! Choose an option from the menu below.",
        reply_markup=main_menu_keyboard(),
    )


def get_start_handler() -> CommandHandler:
    return CommandHandler("start", start_command)
