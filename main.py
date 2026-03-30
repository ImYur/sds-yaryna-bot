import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

DESIGNER_ID = int(os.getenv("DESIGNER_ID"))
MANAGERS = [int(x) for x in os.getenv("MANAGER_IDS").split(",")]

CHAT_MODE = {}

keyboard = [["💬 Чатик", "📂 Проекти"]]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт 👋", reply_markup=reply_markup)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in MANAGERS:
        text = update.message.text

        if text == "💬 Чатик":
            CHAT_MODE[user_id] = True
            await update.message.reply_text("Ти в чаті з дизайнером ✍️")
            return

        if CHAT_MODE.get(user_id):
            await context.bot.send_message(
                chat_id=DESIGNER_ID,
                text=f"Менеджер:\n{text}"
            )

    elif user_id == DESIGNER_ID:
        text = update.message.text

        for manager in MANAGERS:
            await context.bot.send_message(
                chat_id=manager,
                text=f"Дизайнер:\n{text}"
            )

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
