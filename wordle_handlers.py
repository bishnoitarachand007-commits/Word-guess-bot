import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    ReactionTypeEmoji,
)

from game import new_game, submit_guess, load_words
from renderer import save_board
from database import (
    add_diamonds,
    add_group_diamonds,
    get_wordle_mode,
    set_wordle_mode,
)
from bot_common import games, is_game_active, send_main_menu
from multi_games_ui import wordle_menu_keyboard, mode_keyboard

DIAMOND_ID = "5298988357538328017"

FEEDBACK = {
    "correct": "🟩",
    "present": "🟨",
    "absent": "🟥",
}


async def show_wordle_menu(chat_id, context):
    mode = get_wordle_mode(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"WORDLE\n\nCurrent mode: {'Image Mode' if mode == 'image' else 'Normal Mode'}",
        reply_markup=wordle_menu_keyboard(mode),
    )


async def show_mode_menu(query, chat_id):
    mode = get_wordle_mode(chat_id)
    await query.edit_message_text(
        "Choose your Wordle mode.\nYour choice is saved until you change it.",
        reply_markup=mode_keyboard(mode),
    )


async def start_wordle(chat_id, context):
    if is_game_active(chat_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="A game is already active in this chat. Finish it before starting another.",
        )
        return

    game = new_game()
    game["type"] = "wordle"
    game["mode"] = get_wordle_mode(chat_id)
    games[chat_id] = game

    await show_wordle_board(chat_id, context, game)

async def show_wordle_board(chat_id, context, game):
    if game["mode"] == "normal":
        lines = [
            "WORDLE — Normal Mode",
            "Guess the hidden 5-letter word.",
            "🟩 Correct   🟨 Misplaced   🟥 Absent",
            f"Attempts: {game['attempts']}/20",
            "",
        ]
        for guess, feedback in game["history"]:
            lines.append(" ".join(FEEDBACK[item] for item in feedback))
            lines.append(guess)
        if game["status"] == "won":
            lines.extend(["", "🎉 YOU WON!", f"Reward: 💎 {game['reward']}"])
        elif game["status"] == "lost":
            lines.extend(["", "GAME OVER", f"Word: {game['secret']}"])
        keyboard = None
        if game["status"] != "playing":
            keyboard = wordle_menu_keyboard(game["mode"])
        text = "\\n".join(lines)
        message_id = game.get("message_id")
        if message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
        else:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
            )
            game["message_id"] = message.message_id
        return

    filename = save_board(
        game["history"],
        filename=f"board_{chat_id}.png",
    )
    caption = f"💎 WORD GUESS\nAttempts: {game['attempts']}/20"
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id=DIAMOND_ID,
        )
    ]

    if game["status"] == "won":
        caption += f"\n\n🎉 YOU WON!\nReward: 💎 {game['reward']}"
        offset = len(caption[:caption.rfind("💎")].encode("utf-16-le")) // 2
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=2,
                custom_emoji_id=DIAMOND_ID,
            )
        )
    elif game["status"] == "lost":
        caption += f"\n\nGAME OVER\nWord: {game['secret']}"

    keyboard = (
        wordle_menu_keyboard(game["mode"])
        if game["status"] != "playing"
        else None
    )

    old_id = game.get("message_id")
    with open(filename, "rb") as photo:
        message = await context.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            caption_entities=entities,
            reply_markup=keyboard,
        )

    game["message_id"] = message.message_id

    if old_id:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=old_id,
            )
        except Exception as error:
            print("Old Wordle board could not be deleted:", error)


async def handle_wordle_callback(query, context):
    chat_id = query.message.chat_id
    data = query.data

    if data == "menu_wordle":
        if is_game_active(chat_id):
            await query.answer("Finish the active game first.", show_alert=True)
            return
        await query.answer()
        await show_wordle_menu(chat_id, context)
        return

    if data == "wordle_modes":
        if is_game_active(chat_id):
            await query.answer("Finish the active game before changing mode.", show_alert=True)
            return
        await query.answer()
        await show_mode_menu(query, chat_id)
        return

    if data in ("mode_normal", "mode_image"):
        if is_game_active(chat_id):
            await query.answer("Finish the active game first.", show_alert=True)
            return
        mode = "normal" if data == "mode_normal" else "image"
        set_wordle_mode(chat_id, mode)
        await query.answer("Mode saved.")
        await query.edit_message_text(
            f"Wordle mode saved: {'Normal Mode' if mode == 'normal' else 'Image Mode'}",
            reply_markup=wordle_menu_keyboard(mode),
        )
        return

    if data == "new_game":
        await query.answer()
        await start_wordle(chat_id, context)
        return

    if data == "main_menu":
        if is_game_active(chat_id):
            await query.answer("Finish the active game before leaving it.", show_alert=True)
            return
        await query.answer()
        await send_main_menu(chat_id, context)
        return


async def handle_wordle_guess(update, context):
    chat = update.effective_chat
    chat_id = chat.id
    game = games.get(chat_id)

    if not game or game.get("type") != "wordle" or game.get("status") != "playing":
        return

    guess = update.message.text.strip().upper()

    if len(guess) != 5 or not guess.isalpha():
        return

    if guess not in load_words():
        await update.message.reply_text("That is not a valid word. Try another 5-letter English word.")
        return

    result = submit_guess(game, guess)

    if result == "invalid":
        await update.message.reply_text("Please enter a valid 5-letter word.")
        return

    await show_wordle_board(chat_id, context, game)

    if result == "won":
        user = update.effective_user
        add_diamonds(user.id, user.full_name, game["reward"])

        if chat.type in ("group", "supergroup"):
            add_group_diamonds(
                chat_id,
                user.id,
                user.full_name,
                game["reward"],
            )

        try:
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=update.message.message_id,
                reaction=[ReactionTypeEmoji(emoji="🎉")],
            )
        except Exception as error:
            print("Reaction could not be added:", error)
