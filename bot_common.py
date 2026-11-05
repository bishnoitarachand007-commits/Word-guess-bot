import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from multi_games_ui import main_menu_keyboard

games = {}
menu_cooldowns = {}
MENU_COOLDOWN_SECONDS = 120

SUPPORT_GROUP_URL = "https://t.me/JarvisGamesChat"

INTRO_TEXT = (
    "🎮 WELCOME TO THE GAME HUB!\n\n"
    "Play Wordle, Sudoku, and Tic Tac Toe with your group.\n\n"
    "Add me to your group and send /start to open the game menu."
)


def is_game_active(chat_id):
    game = games.get(chat_id)
    return bool(game and game.get("status") in ("playing", "waiting"))


async def send_main_menu(chat_id, context, text="🎮 GAME MENU\n\nChoose a game:"):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=main_menu_keyboard(),
    )


async def get_intro_keyboard(context):
    me = await context.bot.get_me()
    add_url = f"https://t.me/{me.username}?startgroup=true"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "➕ Add me to group",
            url=add_url,
            style="primary",
        )],
        [InlineKeyboardButton(
            "💬 Support group",
            url=SUPPORT_GROUP_URL,
            style="primary",
        )],
    ])


async def send_intro(chat_id, context):
    await context.bot.send_message(
        chat_id=chat_id,
        text=INTRO_TEXT,
        reply_markup=await get_intro_keyboard(context),
    )


def check_menu_cooldown(chat_id, user_id, action='games'):
    now = time.monotonic()
    key = (chat_id, user_id, action)
    last_used = menu_cooldowns.get(key, 0)
    remaining = MENU_COOLDOWN_SECONDS - (now - last_used)
    if remaining > 0:
        return int(remaining) + 1
    menu_cooldowns[key] = now
    return 0
