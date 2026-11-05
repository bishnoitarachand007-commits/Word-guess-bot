import os
import asyncio

from dotenv import load_dotenv
from telegram import Update, MessageEntity
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from database import (
    init_db,
    add_diamonds,
    get_top,
    add_group_diamonds,
    get_group_top,
)
from bot_common import games, send_main_menu, send_intro
from wordle_handlers import (
    handle_wordle_callback,
    handle_wordle_guess,
)
from multi_game_handlers import (
    handle_multi_game_callback,
    handle_sudoku_text,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

MEDALS = [
    "4978994451964757181",
    "5447203607294265305",
    "5453902265922376865",
]
DIAMOND_ID = "5298988357538328017"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await send_intro(chat.id, context)
    else:
        await send_main_menu(chat.id, context)


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await send_intro(chat.id, context)
    else:
        await send_main_menu(chat.id, context)


def make_ranking(players, title):
    text = ""
    entities = []

    def add(value):
        nonlocal text
        text += value

    def add_custom(placeholder, emoji_id):
        offset = len(text.encode("utf-16-le")) // 2
        add(placeholder)
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=2,
                custom_emoji_id=emoji_id,
            )
        )

    add_custom("💎", DIAMOND_ID)
    add(f" {title}\n\n")

    for i, (name, diamonds) in enumerate(players, 1):
        if i <= 3:
            add_custom(["🥇", "🥈", "🥉"][i - 1], MEDALS[i - 1])
        else:
            add(f"{i}.")

        safe_name = name.replace("\n", " ").replace("\r", " ")
        add(f" {safe_name} — ")
        add_custom("💎", DIAMOND_ID)
        add(f" {diamonds}\n")

    return text.rstrip(), entities


async def send_ranking(update, players, title):
    if not players:
        await update.message.reply_text("The leaderboard is empty!")
        return

    text, entities = make_ranking(players, title)
    await update.message.reply_text(text, entities=entities)


async def globaltop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_ranking(update, get_top(10), "GLOBAL TOP 10")


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Use /top in a group to view its leaderboard."
        )
        return

    await send_ranking(update, get_group_top(chat.id, 10), "GROUP TOP 10")


async def bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    members = update.message.new_chat_members

    if any(member.id == context.bot.id for member in members):
        await send_main_menu(update.effective_chat.id, context)


async def callback_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    data = update.callback_query.data

    if data.startswith(("menu_sudoku", "menu_ttt", "ttt_", "game_cancel")):
        await handle_multi_game_callback(update.callback_query, context)
    else:
        await handle_wordle_callback(update.callback_query, context)


async def text_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)

    if not game:
        return

    if game.get("type") == "sudoku":
        await handle_sudoku_text(update, context)
    elif game.get("type") == "wordle":
        await handle_wordle_guess(update, context)


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("globaltop", globaltop_command))

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
    )

    print("Game bot is running...")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
