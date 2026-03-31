import os
import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DESIGNER_ID = int(os.getenv("DESIGNER_ID"))
MANAGER_IDS = [int(x.strip()) for x in os.getenv("MANAGER_IDS", "").split(",") if x.strip()]

# ТУТ СТАВИШ СВОЇ ІМЕНА
USER_NAMES = {
    911772912: "Юра",
    766774400: "Маркіян",
    331127622: "Елла",
    540170329: "Семен",
}

ALL_USERS = list(dict.fromkeys(MANAGER_IDS + [DESIGNER_ID]))

DATA_FILE = Path("data.json")

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["💬 Чатик", "📁 Папки"], ["🗄 Архів", "🏠 Головне меню"]],
    resize_keyboard=True
)

USER_STATE = {}   # chat / folder / awaiting_folder_name / idle
USER_FOLDER = {}  # user_id -> folder_id


def now_str() -> str:
    return datetime.now().strftime("%d.%m %H:%M")


def user_name(user_id: int) -> str:
    return USER_NAMES.get(user_id, str(user_id))


def load_data():
    if not DATA_FILE.exists():
        return {
            "folders": {},
            "chat": []
        }
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "folders": {},
            "chat": []
        }


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


DATA = load_data()


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


def active_folders():
    return {k: v for k, v in DATA["folders"].items() if not v.get("archived", False)}


def archived_folders():
    return {k: v for k, v in DATA["folders"].items() if v.get("archived", False)}


def build_folder_buttons(folder_dict, prefix: str):
    rows = []
    for folder_id, folder in folder_dict.items():
        rows.append([InlineKeyboardButton(folder["name"], callback_data=f"{prefix}:{folder_id}")])
    return rows


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE[update.effective_user.id] = "idle"
    USER_FOLDER.pop(update.effective_user.id, None)
    await update.message.reply_text("Привіт 👋", reply_markup=MAIN_KEYBOARD)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE[update.effective_user.id] = "idle"
    USER_FOLDER.pop(update.effective_user.id, None)
    await update.message.reply_text("Головне меню", reply_markup=MAIN_KEYBOARD)


async def show_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE[update.effective_user.id] = "chat"
    USER_FOLDER.pop(update.effective_user.id, None)
    await update.message.reply_text("Ти в Чатику 💬")


async def show_folders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    folders = active_folders()
    buttons = [[InlineKeyboardButton("➕ Нова папка", callback_data="folder_create")]]

    if folders:
        buttons += build_folder_buttons(folders, "folder_open")

    await update.message.reply_text(
        "Активні папки:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def show_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    folders = archived_folders()
    if not folders:
        await update.message.reply_text("Архів порожній.")
        return

    buttons = build_folder_buttons(folders, "folder_restore_open")
    await update.message.reply_text(
        "Архівні папки:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


def format_folder_history(folder_id: str, limit: int = 15) -> str:
    folder = DATA["folders"][folder_id]
    msgs = folder.get("messages", [])
    text = f"📁 {folder['name']}\n\n"

    if not msgs:
        text += "Поки що порожньо."
        return text

    for m in msgs[-limit:]:
        line = f"{m['time']} | {m['author']}: {m['text']}"
        text += line + "\n"

    return text[:3900]


def folder_actions_markup(folder_id: str, archived: bool = False):
    if archived:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("♻️ Повернути", callback_data=f"folder_restore:{folder_id}")]
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Оновити історію", callback_data=f"folder_open:{folder_id}")],
        [InlineKeyboardButton("📎 Останні файли", callback_data=f"folder_files:{folder_id}")],
        [InlineKeyboardButton("📦 Архівувати", callback_data=f"folder_archive:{folder_id}")]
    ])


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data_cb = query.data

    if data_cb == "folder_create":
        USER_STATE[user_id] = "awaiting_folder_name"
        USER_FOLDER.pop(user_id, None)
        await query.message.reply_text("Напиши назву нової папки.")
        return

    if data_cb.startswith("folder_open:"):
        folder_id = data_cb.split(":", 1)[1]
        if folder_id not in DATA["folders"]:
            await query.message.reply_text("Папку не знайдено.")
            return

        USER_STATE[user_id] = "folder"
        USER_FOLDER[user_id] = folder_id

        await query.message.reply_text(
            format_folder_history(folder_id),
            reply_markup=folder_actions_markup(folder_id)
        )
        return

    if data_cb.startswith("folder_archive:"):
        folder_id = data_cb.split(":", 1)[1]
        if folder_id in DATA["folders"]:
            DATA["folders"][folder_id]["archived"] = True
            save_data(DATA)
            if USER_FOLDER.get(user_id) == folder_id:
                USER_FOLDER.pop(user_id, None)
                USER_STATE[user_id] = "idle"
            await query.message.reply_text("Папку заархівовано.")
        return

    if data_cb.startswith("folder_restore_open:"):
        folder_id = data_cb.split(":", 1)[1]
        if folder_id not in DATA["folders"]:
            await query.message.reply_text("Папку не знайдено.")
            return

        await query.message.reply_text(
            format_folder_history(folder_id),
            reply_markup=folder_actions_markup(folder_id, archived=True)
        )
        return

    if data_cb.startswith("folder_restore:"):
        folder_id = data_cb.split(":", 1)[1]
        if folder_id in DATA["folders"]:
            DATA["folders"][folder_id]["archived"] = False
            save_data(DATA)
            await query.message.reply_text("Папку повернуто з архіву.")
        return

    if data_cb.startswith("folder_files:"):
        folder_id = data_cb.split(":", 1)[1]
        folder = DATA["folders"].get(folder_id)
        if not folder:
            await query.message.reply_text("Папку не знайдено.")
            return

        files = [m for m in folder.get("messages", []) if m.get("kind") in {"photo", "document", "voice", "video"}]
        if not files:
            await query.message.reply_text("У цій папці поки немає файлів.")
            return

        recent = files[-10:]
        await query.message.reply_text(f"Надсилаю останні файли з папки {folder['name']}.")

        for item in recent:
            caption = f"{item['time']} | {item['author']}"
            kind = item["kind"]
            file_id = item["file_id"]

            try:
                if kind == "photo":
                    await context.bot.send_photo(chat_id=user_id, photo=file_id, caption=caption)
                elif kind == "document":
                    await context.bot.send_document(chat_id=user_id, document=file_id, caption=caption)
                elif kind == "voice":
                    await context.bot.send_voice(chat_id=user_id, voice=file_id, caption=caption)
                elif kind == "video":
                    await context.bot.send_video(chat_id=user_id, video=file_id, caption=caption)
            except Exception:
                pass
        return


def make_folder_id(name: str) -> str:
    base = name.strip()
    idx = 1
    while f"f{idx}" in DATA["folders"]:
        idx += 1
    return f"f{idx}"


async def send_to_all_except_sender(context: ContextTypes.DEFAULT_TYPE, sender_id: int, text: str):
    for uid in ALL_USERS:
        if uid != sender_id:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
            except Exception:
                pass


async def forward_media_to_all_except_sender(context: ContextTypes.DEFAULT_TYPE, sender_id: int, kind: str, file_id: str, caption: str | None = None):
    for uid in ALL_USERS:
        if uid == sender_id:
            continue
        try:
            if kind == "photo":
                await context.bot.send_photo(chat_id=uid, photo=file_id, caption=caption)
            elif kind == "document":
                await context.bot.send_document(chat_id=uid, document=file_id, caption=caption)
            elif kind == "voice":
                await context.bot.send_voice(chat_id=uid, voice=file_id, caption=caption)
            elif kind == "video":
                await context.bot.send_video(chat_id=uid, video=file_id, caption=caption)
        except Exception:
            pass


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    name = user_name(user_id)

    if text == "/start":
        await start(update, context)
        return

    if text == "🏠 Головне меню":
        await main_menu(update, context)
        return

    if text == "💬 Чатик":
        await show_chat(update, context)
        return

    if text == "📁 Папки":
        await show_folders(update, context)
        return

    if text == "🗄 Архів":
        await show_archive(update, context)
        return

    state = USER_STATE.get(user_id, "idle")

    if state == "awaiting_folder_name":
        folder_name = text
        folder_id = make_folder_id(folder_name)
        DATA["folders"][folder_id] = {
            "name": folder_name,
            "archived": False,
            "messages": []
        }
        save_data(DATA)

        USER_STATE[user_id] = "folder"
        USER_FOLDER[user_id] = folder_id

        await update.message.reply_text(f"Папку '{folder_name}' створено.")
        await update.message.reply_text(
            format_folder_history(folder_id),
            reply_markup=folder_actions_markup(folder_id)
        )
        return

    if state == "chat":
        msg = {
            "time": now_str(),
            "author": name,
            "text": text
        }
        DATA["chat"].append(msg)
        save_data(DATA)

        await send_to_all_except_sender(
            context,
            user_id,
            f"💬 Чатик\n{msg['time']} | {name}: {text}"
        )
        return

    if state == "folder":
        folder_id = USER_FOLDER.get(user_id)
        if not folder_id or folder_id not in DATA["folders"]:
            await update.message.reply_text("Спочатку відкрий папку.")
            return

        entry = {
            "time": now_str(),
            "author": name,
            "text": text,
            "kind": "text"
        }
        DATA["folders"][folder_id]["messages"].append(entry)
        save_data(DATA)

        await send_to_all_except_sender(
            context,
            user_id,
            f"📁 {DATA['folders'][folder_id]['name']}\n{entry['time']} | {name}: {text}"
        )
        return

    await update.message.reply_text("Обери: 💬 Чатик або 📁 Папки")


async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = USER_STATE.get(user_id, "idle")
    name = user_name(user_id)

    if state != "folder":
        await update.message.reply_text("Файли можна надсилати тільки всередині папки.")
        return

    folder_id = USER_FOLDER.get(user_id)
    if not folder_id or folder_id not in DATA["folders"]:
        await update.message.reply_text("Спочатку відкрий папку.")
        return

    kind = None
    file_id = None
    label = "Файл"

    if update.message.photo:
        kind = "photo"
        file_id = update.message.photo[-1].file_id
        label = "Фото"
    elif update.message.document:
        kind = "document"
        file_id = update.message.document.file_id
        label = update.message.document.file_name or "Документ"
    elif update.message.voice:
        kind = "voice"
        file_id = update.message.voice.file_id
        label = "Voice"
    elif update.message.video:
        kind = "video"
        file_id = update.message.video.file_id
        label = update.message.video.file_name or "Відео"

    if not kind or not file_id:
        return

    entry = {
        "time": now_str(),
        "author": name,
        "text": f"[{label}]",
        "kind": kind,
        "file_id": file_id
    }
    DATA["folders"][folder_id]["messages"].append(entry)
    save_data(DATA)

    caption = f"📁 {DATA['folders'][folder_id]['name']}\n{entry['time']} | {name}: {label}"
    await forward_media_to_all_except_sender(context, user_id, kind, file_id, caption)


def main():
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.VIDEO, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
