import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
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


# 👉 фейковий сервер для Render
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


# 👉 логіка бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт 👋", reply_markup=reply_markup)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    text = update.message.text or ""

    if user_id in MANAGER_IDS:
        if text == "💬 Чатик":
            CHAT_MODE[user_id] = True
            await update.message.reply_text("Ти в чаті з дизайнером ✍️")
            return

        if CHAT_MODE.get(user_id):
            await context.bot.send_message(
                chat_id=DESIGNER_ID,
                text=f"Менеджер:\n{text}"
            )
        return

    if user_id == DESIGNER_ID:
        for manager in MANAGER_IDS:
            await context.bot.send_message(
                chat_id=manager,
                text=f"Дизайнер:\n{text}"
            )


# 👉 запуск
def main():
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
