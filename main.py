import os
from text_style import bold_text
import asyncio
from aiohttp import web

from dotenv import load_dotenv
from telegram import Update, User, MessageEntity, InlineKeyboardButton, InlineKeyboardMarkup
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
    get_higher_lower_top,
    get_higher_lower_group_top,
    get_wordle_profile,
    get_wordle_group_profile,
    get_higher_lower_profile,
    get_higher_lower_group_profile,
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
    cancel_ttt_wait,
)
import nox_handlers as nox
import nox_miniapp_server as nox_web

from higher_lower_handlers import (
    handle_higher_lower_callback,
    handle_higher_lower_text,
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
    game_type = game.get("type")
    if game_type == "tictactoe":
        cancel_ttt_wait(game)
    game["status"] = "ended"
    if game_type == "tictactoe":
        callback = "ttt_restart"
    elif game_type == "higher_lower":
        callback = "hl_restart"
    else:
        callback = "new_game"
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
    add(f" {bold_text(title)}\n\n")

    for i, (user_id, name, diamonds) in enumerate(players, 1):
        if i <= 3:
            add_custom(["🥇", "🥈", "🥉"][i - 1], MEDALS[i - 1])
        else:
            add(f"{i}.")

        add(" ")
        safe_name = (name or "Player").replace("\n", " ").replace("\r", " ")
        offset = len(text.encode("utf-16-le")) // 2
        add(safe_name)

        entities.append(
            MessageEntity(
                type="text_mention",
                offset=offset,
                length=len(safe_name.encode("utf-16-le")) // 2,
                user=User(id=user_id, first_name=safe_name, is_bot=False),
            )
        )

        add(" — ")
        add_custom("💎", DIAMOND_ID)
        add(f" {diamonds}\n")

    return text.rstrip(), entities


async def send_ranking(update, players, title):
    if not players:
        await update.message.reply_text("The leaderboard is empty!")
        return

    text, entities = make_ranking(players, title)
    await update.message.reply_text(text, entities=entities)


def leaderboard_keyboard(scope):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Wordle", callback_data=f"lb_{scope}_wordle"),
            InlineKeyboardButton("Higher / Lower", callback_data=f"lb_{scope}_hl"),
        ],
        [InlineKeyboardButton("Back", callback_data="lb_back")],
    ])


async def globaltop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🏆 {bold_text('GLOBAL LEADERBOARD')}\n\nChoose a game:",
        reply_markup=leaderboard_keyboard("global"),
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Use /top in a group to view its leaderboard."
        )
        return

    await update.message.reply_text(
        f"🏆 {bold_text('GROUP LEADERBOARD')}\n\nChoose a game:",
        reply_markup=leaderboard_keyboard("group"),
    )


async def leaderboard_callback(query):
    data = query.data

    if data == "lb_back":
        await query.answer()
        await query.edit_message_text("Leaderboard menu closed.")
        return

    if data in ("lb_menu_global", "lb_menu_group"):
        scope = data.removeprefix("lb_menu_")
        title = "GLOBAL LEADERBOARD" if scope == "global" else "GROUP LEADERBOARD"
        await query.answer()
        await query.edit_message_text(
            f"🏆 {bold_text(title)}\n\nChoose a game:",
            reply_markup=leaderboard_keyboard(scope),
        )
        return

    parts = data.split("_")
    if len(parts) != 3 or parts[0] != "lb":
        await query.answer("Invalid leaderboard option.", show_alert=True)
        return

    scope, game = parts[1], parts[2]
    chat_id = query.message.chat_id

    if scope == "global":
        if game == "wordle":
            players, title = get_top(10), "GLOBAL WORDLE TOP 10"
        elif game == "hl":
            players, title = get_higher_lower_top(10), "GLOBAL HIGHER / LOWER TOP 10"
        else:
            await query.answer("Unknown game.", show_alert=True)
            return
    elif scope == "group":
        if game == "wordle":
            players, title = get_group_top(chat_id, 10), "GROUP WORDLE TOP 10"
        elif game == "hl":
            players, title = get_higher_lower_group_top(chat_id, 10), "GROUP HIGHER / LOWER TOP 10"
        else:
            await query.answer("Unknown game.", show_alert=True)
            return
    else:
        await query.answer("Invalid leaderboard.", show_alert=True)
        return

    await query.answer()

    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⬅️ Back to Games",
            callback_data=f"lb_menu_{scope}",
        )]
    ])

    if not players:
        await query.edit_message_text(
            "This leaderboard is empty.",
            reply_markup=back_keyboard,
        )
        return

    ranking_text, entities = make_ranking(players, title)
    await query.edit_message_text(
        text=ranking_text,
        entities=entities,
        reply_markup=back_keyboard,
    )


def profile_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Wordle", callback_data="profile_wordle"),
            InlineKeyboardButton("Higher / Lower", callback_data="profile_hl"),
        ]
    ])


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👤 YOUR PROFILE\n\nChoose a game:",
        reply_markup=profile_keyboard(),
    )


async def profile_callback(query):
    data = query.data
    user_id = query.from_user.id
    chat = query.message.chat

    if data == "profile_back":
        await query.answer()
        await query.edit_message_text(
            "👤 YOUR PROFILE\n\nChoose a game:",
            reply_markup=profile_keyboard(),
        )
        return

    if data == "profile_wordle":
        game_name = "Wordle"
        global_stats = get_wordle_profile(user_id)
        group_stats = (
            get_wordle_group_profile(chat.id, user_id)
            if chat.type in ("group", "supergroup") else None
        )
    elif data == "profile_hl":
        game_name = "Higher / Lower"
        global_stats = get_higher_lower_profile(user_id)
        group_stats = (
            get_higher_lower_group_profile(chat.id, user_id)
            if chat.type in ("group", "supergroup") else None
        )
    else:
        await query.answer("Invalid profile option.", show_alert=True)
        return

    def format_stats(stats):
        if stats is None:
            return "0 diamonds | Unranked"
        return f"{stats['diamonds']:,} diamonds | Rank #{stats['rank']}"

    lines = [
        f"👤 {query.from_user.full_name}'s {game_name} Profile",
        "",
        f"🌍 Global: {format_stats(global_stats)}",
    ]

    if chat.type in ("group", "supergroup"):
        lines.append(f"👥 This group: {format_stats(group_stats)}")
    else:
        lines.append("👥 Group stats: Use /profile inside a group to view them.")

    lines.extend([
        "",
        "🏘️ Distinct groups played: Not tracked yet",
    ])

    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Games", callback_data="profile_back")]
    ])

    await query.answer()
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=back_keyboard,
    )


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
    if data.startswith(("nox_turn:", "nox_card:", "nox_join:", "nox_hoststart:")):
        await nox.nox_callback(update, context)
        return

    if data in ("menu_wordle", "menu_sudoku", "menu_ttt", "menu_higher_lower"):
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

    if data.startswith("profile_"):
        await profile_callback(update.callback_query)
    elif data.startswith("lb_"):
        await leaderboard_callback(update.callback_query)
    elif data.startswith(("menu_higher_lower", "hl_")):
        await handle_higher_lower_callback(update.callback_query, context)
    elif data.startswith(("menu_sudoku", "menu_ttt", "ttt_", "game_cancel")):
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
    elif game.get("type") == "higher_lower":
        await handle_higher_lower_text(update, context)


async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # Count private interactions and intentional group interactions only.
    should_track = bool(chat and chat.type == "private")

    if chat and chat.type in ("group", "supergroup"):
        message = update.effective_message
        is_group_command = bool(
            message and any(
                entity.type == "bot_command"
                for entity in (message.entities or [])
            )
        )
        is_admin_command = bool(
            message and message.text and message.text.strip().startswith("!")
        )
        should_track = bool(
            update.callback_query or is_group_command or is_admin_command
        )

    if user and not user.is_bot and should_track:
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
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("end", end_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("globaltop", globaltop_command))
    app.add_handler(CommandHandler("noxnew", nox.nox_new))
    app.add_handler(CommandHandler("noxtournament", nox.nox_tournament))
    app.add_handler(CommandHandler("noxjoin", nox.nox_join))
    app.add_handler(CommandHandler("noxleave", nox.nox_leave))
    app.add_handler(CommandHandler("noxstartgame", nox.nox_start_game))
    app.add_handler(CommandHandler("noxgameend", nox.nox_game_end))
    app.add_handler(CommandHandler("noxcancel", nox.nox_cancel))
    app.add_handler(CommandHandler("noxwallet", nox.nox_wallet))
    app.add_handler(CommandHandler("noxpay", nox.nox_pay))
    app.add_handler(CommandHandler("noxdaily", nox.nox_daily))
    app.add_handler(CommandHandler("noxclaim", nox.nox_claim))
    app.add_handler(CommandHandler("noxtoprich", nox.nox_toprich))
    app.add_handler(CommandHandler("noxglobaltoprich", nox.nox_globaltoprich))
    app.add_handler(CommandHandler("noxstats", nox.nox_stats))
    app.add_handler(CommandHandler("noxreset", nox.nox_reset))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!"), admin_command_router))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
    )

    runner = None
    initialized = False
    started = False
    polling = False

    try:
        await app.initialize()
        initialized = True

        await app.start()
        started = True

        web_app = nox_web.build_web_app(
            app.bot,
            nox.ACTIVE_GAMES,
            nox.process_card_pass,
            TOKEN,
        )
        runner = web.AppRunner(web_app)
        await runner.setup()
        port = int(os.environ.get("PORT", "3000"))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        await app.updater.start_polling()
        polling = True
        print("Telegram bot and NOX Mini App backend are running.")

        await asyncio.Event().wait()
    finally:
        if polling:
            await app.updater.stop()
        if runner is not None:
            await runner.cleanup()
        if started:
            await app.stop()
        if initialized:
            await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
