from __future__ import annotations

import io
import re
from typing import Any

import httpx
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from telegram import InputFile, ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import API_BASE_URL
from bot.handlers.start import fetch_events
from bot.keyboards import (
    BTN_BACK_MENU,
    BTN_CANCEL,
    BTN_CONFIRM,
    BTN_REGISTER,
    confirm_cancel_keyboard,
    event_picker_keyboard,
    main_menu_keyboard,
)
from bot.states import REG_CONFIRM, REG_EMAIL, REG_EVENT, REG_NAME, REG_PHONE

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{7,20}$")

REGISTRATIONS_ENDPOINT = f"{API_BASE_URL.rstrip('/')}/registrations"
HTTP_TIMEOUT_SECONDS = 10.0

QR_FILL_COLOR = "#0F172A"
QR_BACK_COLOR = "#E6FFFA"


# Purpose: Clear temporary registration data from user conversation state.
def _clear_registration_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        "event_options",
        "selected_event_id",
        "selected_event_title",
        "reg_name",
        "reg_email",
        "reg_phone",
    ):
        context.user_data.pop(key, None)


# Purpose: Build a label-to-event lookup from API event rows.
def _build_event_options(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    options: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = str(event.get("id", "")).strip()
        title = str(event.get("title", "Untitled Event")).strip()
        location = str(event.get("location", "TBA")).strip()
        label = f"{title} ({location})"
        if label in options:
            label = f"{title} [{event_id}]"
        options[label] = event
    return options


# Purpose: Extract readable API error details from failed HTTP responses.
def _extract_api_error(exc: httpx.HTTPStatusError) -> str:
    try:
        payload = exc.response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
    except ValueError:
        pass
    return "Request failed"


# Purpose: Create or update a registration via the backend API.
async def _upsert_registration(
    *,
    event_id: str,
    telegram_user_id: int,
    full_name: str,
    email: str,
    phone: str,
) -> str:
    payload = {
        "event_id": event_id,
        "telegram_user_id": telegram_user_id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = await client.post(REGISTRATIONS_ENDPOINT, json=payload)
    response.raise_for_status()

    data = response.json()
    registration_id = data.get("registration_id") if isinstance(data, dict) else None
    if not isinstance(registration_id, str) or not registration_id.strip():
        raise ValueError("registration_id missing in API response")
    return registration_id.strip()


# Purpose: Request QR token creation for a registration from the API.
async def _generate_qr_token(registration_id: str) -> str:
    url = f"{REGISTRATIONS_ENDPOINT}/{registration_id}/qr"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = await client.post(url)
    response.raise_for_status()

    data = response.json()
    qr_token = data.get("qr_token") if isinstance(data, dict) else None
    if not isinstance(qr_token, str) or not qr_token.strip():
        raise ValueError("qr_token missing in API response")
    return qr_token.strip()


# Purpose: Generate a styled QR PNG image from a QR token string.
def _build_styled_qr_png(qr_token: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=12,
        border=2,
    )
    qr.add_data(qr_token)
    qr.make(fit=True)

    image = qr.make_image(fill_color=QR_FILL_COLOR, back_color=QR_BACK_COLOR)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# Purpose: Start registration flow by loading events and prompting selection.
async def register_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    _clear_registration_data(context)

    try:
        events = await fetch_events()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
        await update.message.reply_text(
            "I could not load events from the API. Please try again soon.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    if not events:
        await update.message.reply_text(
            "No open events are available right now.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    options = _build_event_options(events)
    context.user_data["event_options"] = options

    await update.message.reply_text(
        "Choose an event to register:",
        reply_markup=event_picker_keyboard(list(options.keys())),
    )
    return REG_EVENT


# Purpose: Capture selected event and advance to name input.
async def select_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return REG_EVENT

    choice = update.message.text.strip()
    if choice.lower() == BTN_CANCEL.lower():
        return await cancel_registration(update, context)

    if choice.lower() == BTN_BACK_MENU.lower():
        _clear_registration_data(context)
        await update.message.reply_text(
            "Back to main menu.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    options = context.user_data.get("event_options")
    if not isinstance(options, dict) or choice not in options:
        labels = list(options.keys()) if isinstance(options, dict) else []
        await update.message.reply_text(
            "Please choose an event from the buttons.",
            reply_markup=event_picker_keyboard(labels),
        )
        return REG_EVENT

    selected_event = options[choice]
    selected_event_id = str(selected_event.get("id", "")).strip()
    selected_event_title = str(selected_event.get("title", "Untitled Event")).strip()
    if not selected_event_id:
        await update.message.reply_text(
            "This event is invalid. Please choose another event.",
            reply_markup=event_picker_keyboard(list(options.keys())),
        )
        return REG_EVENT

    context.user_data["selected_event_id"] = selected_event_id
    context.user_data["selected_event_title"] = selected_event_title

    await update.message.reply_text(
        f"Great, you selected: {selected_event_title}\nWhat is your full name?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REG_NAME


# Purpose: Validate and store the registrant name.
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


# Purpose: Validate and store the registrant email.
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


# Purpose: Validate phone and present final confirmation summary.
async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return REG_PHONE

    phone = update.message.text.strip()
    if not _PHONE_PATTERN.fullmatch(phone):
        await update.message.reply_text("Please enter a valid phone number.")
        return REG_PHONE

    context.user_data["reg_phone"] = phone

    event_title = str(context.user_data.get("selected_event_title", "Untitled Event"))
    name = str(context.user_data.get("reg_name", ""))
    email = str(context.user_data.get("reg_email", ""))
    summary = (
        "Please confirm your registration details:\n\n"
        f"Event: {event_title}\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Phone: {phone}\n\n"
        f"Tap {BTN_CONFIRM} to submit or {BTN_CANCEL} to abort."
    )

    await update.message.reply_text(summary, reply_markup=confirm_cancel_keyboard())
    return REG_CONFIRM


# Purpose: Submit registration to API and send QR confirmation to user.
async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    user = update.effective_user
    event_id = str(context.user_data.get("selected_event_id", "")).strip()
    event_title = str(context.user_data.get("selected_event_title", "Untitled Event")).strip()
    full_name = str(context.user_data.get("reg_name", "")).strip()
    email = str(context.user_data.get("reg_email", "")).strip()
    phone = str(context.user_data.get("reg_phone", "")).strip()

    if user is None or not event_id or not full_name or not email or not phone:
        _clear_registration_data(context)
        await update.message.reply_text(
            "Missing registration details. Please run Register again.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    try:
        registration_id = await _upsert_registration(
            event_id=event_id,
            telegram_user_id=user.id,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        qr_token = await _generate_qr_token(registration_id)
    except httpx.HTTPStatusError as exc:
        _clear_registration_data(context)
        await update.message.reply_text(
            f"Registration failed: {_extract_api_error(exc)}",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END
    except (httpx.RequestError, ValueError):
        _clear_registration_data(context)
        await update.message.reply_text(
            "Could not reach registration service right now. Please try again.",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    _clear_registration_data(context)
    caption = (
        "Registration successful.\n"
        f"Event: {event_title}\n"
        f"Registration ID: {registration_id}\n"
        "Show this QR code at check-in."
    )

    try:
        qr_png = _build_styled_qr_png(qr_token)
        await update.message.reply_photo(
            photo=InputFile(io.BytesIO(qr_png), filename=f"{registration_id}.png"),
            caption=caption,
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await update.message.reply_text(
            f"{caption}\nQR Token: {qr_token}",
            reply_markup=main_menu_keyboard(),
        )
    return ConversationHandler.END


# Purpose: Cancel the registration flow and return to main menu.
async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    _clear_registration_data(context)
    await update.message.reply_text(
        "Registration cancelled.",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


# Purpose: Re-prompt user when confirmation input is invalid.
async def invalid_confirm_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.message is not None:
        await update.message.reply_text(
            f"Please tap {BTN_CONFIRM} or {BTN_CANCEL}.",
            reply_markup=confirm_cancel_keyboard(),
        )
    return REG_CONFIRM


# Purpose: Build the full registration conversation handler graph.
def get_register_conversation_handler() -> ConversationHandler:
    cancel_regex = re.escape(BTN_CANCEL)
    confirm_regex = re.escape(BTN_CONFIRM)

    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_REGISTER)}$"), register_entry),
            CommandHandler("register", register_entry),
        ],
        states={
            REG_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_event)],
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
            REG_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_phone)],
            REG_CONFIRM: [
                MessageHandler(filters.Regex(f"(?i)^{confirm_regex}$"), confirm_registration),
                MessageHandler(filters.Regex(f"(?i)^{cancel_regex}$"), cancel_registration),
                MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_confirm_choice),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_registration),
            MessageHandler(filters.Regex(f"(?i)^{cancel_regex}$"), cancel_registration),
        ],
        allow_reentry=True,
    )
