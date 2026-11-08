import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity

from multi_games_ui import main_menu_keyboard

games = {}
menu_cooldowns = {}
MENU_COOLDOWN_SECONDS = 0

SUPPORT_GROUP_URL = "https://t.me/JarvisGamesChat"

WELCOME_EMOJI_ID = "5895425908973506277"
HELP_EMOJI_ID = "5220108512893344933"

def build_intro(user):
    name = user.full_name or user.first_name or "Player"
    text = f"Hello {name}! 🤔\nUse /help to know more about the bot. 🆘"

    name_offset = len("Hello ".encode("utf-16-le")) // 2
    name_length = len(name.encode("utf-16-le")) // 2
    welcome_offset = len(f"Hello {name}! ".encode("utf-16-le")) // 2
    help_offset = len(f"Hello {name}! 🤔\nUse /help to know more about the bot. ".encode("utf-16-le")) // 2

    entities = [
        MessageEntity(type=MessageEntity.TEXT_MENTION, offset=name_offset, length=name_length, user=user),
        MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=welcome_offset, length=2, custom_emoji_id=WELCOME_EMOJI_ID),
        MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=help_offset, length=2, custom_emoji_id=HELP_EMOJI_ID),
    ]
    return text, entities


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


async def send_intro(chat_id, context, user):
    text, entities = build_intro(user)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        entities=entities,
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
