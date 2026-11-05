import os
import asyncio

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReactionTypeEmoji,
    MessageEntity,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from game import new_game, submit_guess, load_words
from renderer import save_board
from database import init_db, add_diamonds, get_top, add_group_diamonds, get_group_top

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

games = {}


def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "START NEW GAME",
            callback_data="new_game",
            style="success",
            icon_custom_emoji_id="5298988357538328017"
        )]
    ])



async def show_board(chat_id, context, game):
    filename = save_board(game["history"])

    caption = (
        f"💎 WORD GUESS\\n"
        f"Attempts: {game['attempts']}/20"
    )

    caption_entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="5298988357538328017",
        )
    ]

    if game["status"] == "won":
        caption += (
            f"\\n\\n🎉 YOU WON!"
            f"\\nReward: 💎 {game['reward']}"
        )
        offset = len(caption[:caption.index("💎", 1)].encode("utf-16-le")) // 2
        caption_entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=2,
                custom_emoji_id="5298988357538328017",
            )
        )

    elif game["status"] == "lost":
        caption += f"\\n\\nGAME OVER\\nWord: {game['secret']}"

    keyboard = get_keyboard() if game["status"] != "playing" else None
    old_id = game.get("message_id")

    with open(filename, "rb") as photo:
        message = await context.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            caption_entities=caption_entities,
            reply_markup=keyboard,
        )

    game["message_id"] = message.message_id

    if old_id:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=old_id,
            )
        except Exception as e:
            print("Old image could not be deleted:", e)


SUPPORT_GROUP_URL = "https://t.me/JarvisGamesChat"

INTRO_TEXT = (
    "🎮 WORD GUESS — HOW TO PLAY\\n\\n"
    "1. Guess the hidden 5-letter word.\\n"
    "2. You get 20 attempts.\\n"
    "3. 🟩 Correct: right letter, right place.\\n"
    "4. 🟨 Present: letter is in the word, different place.\\n"
    "5. ⬛ Absent: letter is not in the word.\\n\\n"
    "Add me to your group, then send /start there to play! 💎"
)

async def get_intro_keyboard(context):
    me = await context.bot.get_me()
    add_url = f"https://t.me/{me.username}?startgroup=true"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to group", url=add_url)],
        [InlineKeyboardButton("💬 Support group", url=SUPPORT_GROUP_URL)],
    ])

async def send_intro(chat_id, context):
    await context.bot.send_message(
        chat_id=chat_id,
        text=INTRO_TEXT,
        reply_markup=await get_intro_keyboard(context),
    )

async def start_group_game(chat_id, context):
    current = games.get(chat_id)
    if current and current.get("status") == "playing":
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎮 Game already chal raha hai! Pehle current game complete karo."
        )
        return

    games[chat_id] = new_game()
    await show_board(chat_id, context, games[chat_id])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await send_intro(chat.id, context)
        return
    await start_group_game(chat.id, context)

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(
            "Pehle mujhe apne chat group mein add karo, phir group mein /new bhejo. 🎮",
            reply_markup=await get_intro_keyboard(context),
        )
        return
    await start_group_game(chat.id, context)

async def new_game_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    current = games.get(chat_id)

    if current and current.get("status") == "playing":
        await query.answer("Pehle current game complete karo!", show_alert=True)
        return

    await query.answer()
    games[chat_id] = new_game()
    await show_board(chat_id, context, games[chat_id])

async def bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if any(member.id == context.bot.id for member in update.message.new_chat_members):
        await send_intro(update.effective_chat.id, context)

MEDALS = [
    "4978994451964757181",
    "5447203607294265305",
    "5453902265922376865",
]
DIAMOND_ID = "5298988357538328017"


def make_ranking(players, title):
    text = ""
    entities = []

    def add(value):
        nonlocal text
        text += value

    def add_custom(placeholder, emoji_id):
        offset = len(text.encode("utf-16-le")) // 2
        add(placeholder)
        entities.append(MessageEntity(
            type="custom_emoji",
            offset=offset,
            length=2,
            custom_emoji_id=emoji_id,
        ))

    add_custom("💎", DIAMOND_ID)
    add(f" {title}\n\n")

    for i, (name, diamonds) in enumerate(players, 1):
        if i <= 3:
            add_custom(["🥇", "🥈", "🥉"][i - 1], MEDALS[i - 1])
        else:
            add(f"{i}.")

        safe_name = name.replace("\\n", " ").replace("\\r", " ")
        add(f" {safe_name} — ")
        add_custom("💎", DIAMOND_ID)
        add(f" {diamonds}\n")

    return text.rstrip(), entities


async def send_ranking(update, players, title):
    if not players:
        await update.message.reply_text("🏆 Abhi leaderboard khaali hai!")
        return

    text, entities = make_ranking(players, title)
    await update.message.reply_text(text, entities=entities)


async def globaltop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_ranking(update, get_top(10), "GLOBAL TOP 10")


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "👥 Group leaderboard dekhne ke liye group mein /top use karo."
        )
        return

    await send_ranking(
        update,
        get_group_top(chat.id, 10),
        "GROUP TOP 10",
    )


async def handle_guess(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        return

    guess = update.message.text.strip().upper()

    if len(guess) != 5 or not guess.isalpha():
        return

    if guess not in load_words():
        await update.message.reply_text("❌ Incorrect word! Ye valid word nahi hai.")
        return

    game = games[chat_id]
    result = submit_guess(game, guess)

    if result == "invalid":
        await update.message.reply_text("5-letter word bhejo!")
        return

    if result == "ended":
        await update.message.reply_text(
            "Game ended. New game ke liye button dabao."
        )
        return

    await show_board(chat_id, context, game)

    if result == "won":
        user = update.effective_user
        add_diamonds(user.id, user.full_name, game["reward"])

        if update.effective_chat.type in ("group", "supergroup"):
            add_group_diamonds(
                chat_id, user.id, user.full_name, game["reward"]
            )

        try:
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=update.message.message_id,
                reaction=[ReactionTypeEmoji(emoji="🎉")],
            )
        except Exception as e:
            print("Reaction could not be added:", e)


async def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("globaltop", globaltop_command))
    app.add_handler(
        CallbackQueryHandler(new_game_button, pattern="^new_game$")
    )
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess)
    )

    print("💎 Word Guess Bot is running...")

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
