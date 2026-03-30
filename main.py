import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DESIGNER_ID = int(os.getenv("DESIGNER_ID"))
MANAGER_IDS = [int(x.strip()) for x in os.getenv("MANAGER_IDS", "").split(",") if x.strip()]

CHAT_MODE = {}

keyboard = [["💬 Чатик", "📂 Проекти"]]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


def run_dummy_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт 👋\nОбери розділ:",
        reply_markup=reply_markup
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    text = update.message.text or ""

    if user_id in MANAGER_IDS:
        if text == "💬 Чатик":
            CHAT_MODE[user_id] = True
            await update.message.reply_text("Ти в чатику з дизайнером ✍️")
            return

        if text == "📂 Проекти":
            await update.message.reply_text("Розділ 'Проекти' поки що в розробці.")
            return

        if CHAT_MODE.get(user_id):
            await context.bot.send_message(
                chat_id=DESIGNER_ID,
                text=f"Менеджер:\n{text}"
            )
        return

    if user_id == DESIGNER_ID:
        if text == "💬 Чатик":
            await update.message.reply_text("Ти в чатику з менеджерами ✍️")
            return

        if text == "📂 Проекти":
            await update.message.reply_text("Розділ 'Проекти' поки що в розробці.")
            return

        for manager_id in MANAGER_IDS:
            await context.bot.send_message(
                chat_id=manager_id,
                text=f"Дизайнер:\n{text}"
            )


def main():
    threading.Thread(target=run_dummy_web_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
