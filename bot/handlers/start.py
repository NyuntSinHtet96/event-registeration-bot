from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import httpx
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import API_BASE_URL
from bot.keyboards import BTN_HELP, BTN_REGISTER, BTN_VIEW_EVENTS, main_menu_keyboard

EVENTS_ENDPOINT = f"{API_BASE_URL.rstrip('/')}/events"
HTTP_TIMEOUT_SECONDS = 10.0


# Purpose: Fetch open events from the FastAPI backend.
async def fetch_events(status: str = "OPEN") -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = await client.get(EVENTS_ENDPOINT, params={"status": status})
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        return []

    return [event for event in payload if isinstance(event, dict)]


# Purpose: Convert an ISO timestamp into a readable label.
def _format_start_time(start_time: Any) -> str:
    if not isinstance(start_time, str) or not start_time:
        return "TBD"

    normalized = start_time.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return start_time


# Purpose: Render event list text for the chat response.
def _render_events(events: list[dict[str, Any]]) -> str:
    lines = ["Available events:"]
    for index, event in enumerate(events, start=1):
        title = str(event.get("title", "Untitled Event"))
        location = str(event.get("location", "TBA"))
        start_label = _format_start_time(event.get("start_time"))
        lines.append(f"{index}. {title} | {start_label} | {location}")
    return "\n".join(lines)


# Purpose: Handle /start and show the main menu keyboard.
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    await update.message.reply_text(
        "Welcome! Use the menu to view events or start registration.",
        reply_markup=main_menu_keyboard(),
    )


# Purpose: Handle the View Events menu action with API data.
async def view_events_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    try:
        events = await fetch_events()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
        await update.message.reply_text(
            "I could not load events from the API right now. Please try again shortly.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if not events:
        await update.message.reply_text(
            "No open events found right now.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await update.message.reply_text(
        _render_events(events),
        reply_markup=main_menu_keyboard(),
    )


# Purpose: Show usage instructions when user requests help.
async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    await update.message.reply_text(
        "How to use this bot:\n"
        f"1) Tap {BTN_VIEW_EVENTS} to see current events\n"
        f"2) Tap {BTN_REGISTER} to register for one event\n"
        "3) Follow the prompts and confirm your details",
        reply_markup=main_menu_keyboard(),
    )


# Purpose: Return handler for the /start command.
def get_start_handler() -> CommandHandler:
    return CommandHandler("start", start_command)


# Purpose: Return handler for View Events menu button taps.
def get_view_events_handler() -> MessageHandler:
    return MessageHandler(filters.Regex(f"^{re.escape(BTN_VIEW_EVENTS)}$"), view_events_message)


# Purpose: Return handler for Help menu button taps.
def get_help_handler() -> MessageHandler:
    return MessageHandler(filters.Regex(f"^{re.escape(BTN_HELP)}$"), help_message)


# Purpose: Return handler for the /help command.
def get_help_command_handler() -> CommandHandler:
    return CommandHandler("help", help_message)
