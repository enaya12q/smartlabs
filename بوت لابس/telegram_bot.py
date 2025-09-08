import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_URL = os.environ.get("API_URL")

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
    exit(1)
if not API_URL:
    logger.error("API_URL environment variable not set.")
    exit(1)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and attempts to log in the user via the website API."""
    if not update.effective_user or not update.message:
        logger.warning("No effective user or message in update.")
        return

    user_telegram_id = update.effective_user.id
    user_first_name = update.effective_user.first_name
    
    logger.info(f"User {user_telegram_id} ({user_first_name}) started the bot.")

    login_api_url = f"{API_URL}/api/login"
    payload = {
        "id": user_telegram_id,
        "first_name": user_first_name,
        # Add other Telegram user data if needed for your /api/login endpoint
        # For simplicity, we're only sending ID and first_name as requested.
        # Note: A real Telegram WebApp login sends more data for hash validation.
        # This bot-initiated login is simplified.
    }

    try:
        response = requests.post(login_api_url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        if data.get("success"):
            message = "✅ تم تسجيل دخولك بنجاح عبر الموقع!"
            logger.info(f"User {user_telegram_id} logged in successfully via API.")
        else:
            message = f"❌ فشل تسجيل الدخول، حاول لاحقًا. (الخطأ: {data.get('message', 'غير معروف')})"
            logger.warning(f"User {user_telegram_id} failed to log in via API: {data.get('message')}")
    except requests.exceptions.RequestException as e:
        message = "❌ فشل تسجيل الدخول، حاول لاحقًا. (خطأ في الاتصال بالخادم)"
        logger.error(f"Error connecting to API for user {user_telegram_id}: {e}")
    except Exception as e:
        message = "❌ فشل تسجيل الدخول، حاول لاحقًا. (خطأ غير متوقع)"
        logger.error(f"Unexpected error during login for user {user_telegram_id}: {e}")

    await update.message.reply_text(message)

def main() -> None:
    """Start the bot."""
    # Ensure TELEGRAM_BOT_TOKEN is not None before building the application
    if TELEGRAM_BOT_TOKEN is None:
        logger.error("TELEGRAM_BOT_TOKEN is None, exiting.")
        exit(1)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()