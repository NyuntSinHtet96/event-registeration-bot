import re

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.keyboards import BTN_REGISTER, main_menu_keyboard
from bot.states import REG_CONFIRM, REG_EMAIL, REG_NAME, REG_PHONE

BTN_CONFIRM = "Confirm"
BTN_CANCEL = "Cancel"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{7,20}$")


def _confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(BTN_CONFIRM), KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _clear_registration_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ("reg_name", "reg_email", "reg_phone"):
        context.user_data.pop(key, None)


async def register_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    _clear_registration_data(context)
    await update.message.reply_text(
        "Great, let us register you. What is your full name?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REG_NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return REG_NAME

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Please enter a valid name.")
        return REG_NAME

    context.user_data["reg_name"] = name
    await update.message.reply_text("Thanks. What is your email address?")
    return REG_EMAIL


async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return REG_EMAIL

    email = update.message.text.strip()
    if not _EMAIL_PATTERN.fullmatch(email):
        await update.message.reply_text("That email looks invalid. Please enter a valid email.")
        return REG_EMAIL

    context.user_data["reg_email"] = email
    await update.message.reply_text("Got it. What is your phone number?")
    return REG_PHONE


async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return REG_PHONE

    phone = update.message.text.strip()
    if not _PHONE_PATTERN.fullmatch(phone):
        await update.message.reply_text("Please enter a valid phone number.")
        return REG_PHONE

    context.user_data["reg_phone"] = phone

    name = context.user_data.get("reg_name", "")
    email = context.user_data.get("reg_email", "")
    summary = (
        "Please confirm your registration details:\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Phone: {phone}\n\n"
        f"Tap {BTN_CONFIRM} to submit or {BTN_CANCEL} to abort."
    )

    await update.message.reply_text(summary, reply_markup=_confirm_keyboard())
    return REG_CONFIRM


async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    _clear_registration_data(context)
    await update.message.reply_text(
        "Registration successful. See you at the event!",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    _clear_registration_data(context)
    await update.message.reply_text(
        "Registration cancelled.",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def invalid_confirm_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.message is not None:
        await update.message.reply_text(
            f"Please tap {BTN_CONFIRM} or {BTN_CANCEL}.",
            reply_markup=_confirm_keyboard(),
        )
    return REG_CONFIRM


def get_register_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_REGISTER)}$"), register_entry),
            CommandHandler("register", register_entry),
        ],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
            REG_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_phone)],
            REG_CONFIRM: [
                MessageHandler(filters.Regex(r"(?i)^confirm$"), confirm_registration),
                MessageHandler(filters.Regex(r"(?i)^cancel$"), cancel_registration),
                MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_confirm_choice),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_registration),
            MessageHandler(filters.Regex(r"(?i)^cancel$"), cancel_registration),
        ],
        allow_reentry=True,
    )
