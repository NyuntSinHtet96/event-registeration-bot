import os


# Purpose: Verify Telegram bot application object can be constructed.
def test_build_application() -> None:
    os.environ.setdefault("BOT_TOKEN", "123456:ci-placeholder-token")
    os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")

    from bot.main import build_application

    app = build_application()
    assert app is not None
