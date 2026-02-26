from collections.abc import Sequence

from telegram import KeyboardButton, ReplyKeyboardMarkup

BTN_VIEW_EVENTS = "View Events"
BTN_REGISTER = "Register"
BTN_HELP = "Help"
BTN_CONFIRM = "Confirm"
BTN_CANCEL = "Cancel"
BTN_BACK_MENU = "Back to Menu"


# Purpose: Build the main menu keyboard shown to all users.
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(BTN_VIEW_EVENTS), KeyboardButton(BTN_REGISTER)],
            [KeyboardButton(BTN_HELP)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# Purpose: Build an event picker keyboard from event label options.
def event_picker_keyboard(event_labels: Sequence[str]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(label)] for label in event_labels]
    rows.append([KeyboardButton(BTN_CANCEL), KeyboardButton(BTN_BACK_MENU)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# Purpose: Build the confirm or cancel keyboard for final confirmation.
def confirm_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(BTN_CONFIRM), KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
