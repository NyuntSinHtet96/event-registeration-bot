import logging

from telegram.ext import Application, CommandHandler

from bot.config import BOT_TOKEN
from bot.handlers.register import cancel_registration, get_register_conversation_handler
from bot.handlers.start import get_start_handler


def build_application() -> Application:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(get_start_handler())
    application.add_handler(get_register_conversation_handler())
    application.add_handler(CommandHandler("cancel", cancel_registration))

    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    application = build_application()
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
