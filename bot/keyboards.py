from telegram import KeyboardButton, ReplyKeyboardMarkup

BTN_VIEW_EVENTS = "View Events"
BTN_REGISTER = "Register"
BTN_HELP = "Help"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(BTN_VIEW_EVENTS), KeyboardButton(BTN_REGISTER)],
            [KeyboardButton(BTN_HELP)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
