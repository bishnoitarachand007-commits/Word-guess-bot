from bot_common import games, is_game_active
from higher_lower import new_higher_lower_game, higher_lower_guess
from multi_games_ui import higher_lower_text, higher_lower_keyboard
from database import (
    add_higher_lower_diamonds,
    add_higher_lower_group_diamonds,
)
from admin_database import record_user


async def start_higher_lower(chat_id, user, context):
    if is_game_active(chat_id):
        return

    game = new_higher_lower_game()
    game["player_names"] = {}
    games[chat_id] = game

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=higher_lower_text(game),
    )
    game["message_id"] = message.message_id


async def handle_higher_lower_text(update, context):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or user.is_bot or not message.text:
        return

    game = games.get(chat.id)
    if not game or game.get("type") != "higher_lower":
        return

    value = message.text.strip()
    if not value.isdigit():
        return

    guess = int(value)
    if not 1 <= guess <= 500:
        await message.reply_text("Please guess a number between 1 and 500.")
        return

    result = higher_lower_guess(game, user.id, guess)
    if result == "ended":
        return

    name = user.full_name or user.first_name or str(user.id)
    game["player_names"][user.id] = name
    if chat.type in ("group", "supergroup"):
        record_user(user.id, name)

    if result == "higher":
        await message.reply_text("⬆️ Higher! Try a bigger number.")
        return

    if result == "lower":
        await message.reply_text("⬇️ Lower! Try a smaller number.")
        return

    if result == "won":
        game["winner_name"] = name
        reward = game["reward"]

        # Global leaderboards
        add_higher_lower_diamonds(user.id, name, reward)

        # Group leaderboards
        if chat.type in ("group", "supergroup"):
            add_higher_lower_group_diamonds(
                chat.id, user.id, name, reward
            )

        await context.bot.edit_message_text(
            chat_id=chat.id,
            message_id=game["message_id"],
            text=higher_lower_text(game),
            reply_markup=higher_lower_keyboard(),
        )
        await message.reply_text("🎉 Correct guess! You won the game!")


async def handle_higher_lower_callback(query, context):
    chat_id = query.message.chat_id
    user = query.from_user
    data = query.data
    game = games.get(chat_id)

    if data == "menu_higher_lower":
        if is_game_active(chat_id):
            await query.answer(
                "Another game is already active in this group.",
                show_alert=True,
            )
            return

        await query.answer("Starting Higher / Lower!")
        await start_higher_lower(chat_id, user, context)
        return

    if data == "hl_restart":
        if (
            not game
            or game.get("type") != "higher_lower"
            or game.get("status") not in ("finished", "ended")
        ):
            await query.answer("This game cannot be restarted yet.", show_alert=True)
            return

        new_game = new_higher_lower_game()
        new_game["player_names"] = {}
        new_game["message_id"] = query.message.message_id
        games[chat_id] = new_game

        await query.answer("New game started!")
        await query.edit_message_text(
            text=higher_lower_text(new_game),
        )
