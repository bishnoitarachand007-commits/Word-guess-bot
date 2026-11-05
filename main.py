import os
import asyncio

from dotenv import load_dotenv
from telegram import Update, MessageEntity, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    TypeHandler,
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
from bot_common import games, send_main_menu, send_intro, check_menu_cooldown
from wordle_handlers import (
    handle_wordle_callback,
    handle_wordle_guess,
)
from admin_database import init_admin_db, record_user, record_chat
from admin_handlers import admin_command_router
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
        await send_intro(chat.id, context, update.effective_user)
    else:
        await update.message.reply_text("Use /games to open the game menu.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 GAME BOT HELP\n\n"
        "/start - Open the welcome screen\n"
        "/games - Open the game menu\n"
        "/new - Open the welcome screen\n"
        "/help - Show this help message\n"
        "/top - View your group leaderboard\n"
        "/globaltop - View the global leaderboard\n"
        "/end - End an active group game (group admins only)"
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await send_intro(chat.id, context, update.effective_user)
    else:
        await update.message.reply_text("Use /games to open the game menu.")


async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await send_intro(chat.id, context, update.effective_user)
        return
    remaining = check_menu_cooldown(chat.id, user.id)
    if remaining:
        await update.message.reply_text(f"Please wait {remaining} seconds before opening the menu again.")
        return
    await send_main_menu(chat.id, context)


async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("/end can only be used in a group.")
        return
    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("Only group admins can use /end.")
        return
    game = games.get(chat.id)
    if not game or game.get("status") not in ("playing", "waiting"):
        await update.message.reply_text("There is no active game to end.")
        return
    game["status"] = "ended"
    game_type = game.get("type")
    callback = "ttt_restart" if game_type == "tictactoe" else "new_game"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("START NEW GAME", callback_data=callback, style="success")]])
    message_id = game.get("message_id")
    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat.id, message_id=message_id,
                text="Game ended by an admin.", reply_markup=keyboard
            )
        except Exception:
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat.id, message_id=message_id,
                    caption="Game ended by an admin.", reply_markup=keyboard
                )
            except Exception as error:
                print("Could not update ended game message:", error)
    await update.message.reply_text("The active game has been ended by an admin.")


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
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Thanks for adding me! Use /games to open the game menu."
        )


async def callback_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    data = update.callback_query.data

    if data in ("menu_wordle", "menu_sudoku", "menu_ttt"):
        remaining = check_menu_cooldown(
            update.callback_query.message.chat_id,
            update.callback_query.from_user.id,
            data,
        )
        if remaining:
            await update.callback_query.answer(
                f"Please wait {remaining} seconds before using this menu again.",
                show_alert=True,
            )
            return

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


async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if user and chat and chat.type == "private":
        name = user.full_name or user.first_name or str(user.id)
        record_user(user.id, name)

    if chat and chat.type in ("group", "supergroup"):
        title = chat.title or str(chat.id)
        record_chat(chat.id, title, chat.type)


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    init_db()
    init_admin_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(TypeHandler(Update, track_activity), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("games", games_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("globaltop", globaltop_command))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!"), admin_command_router))
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
