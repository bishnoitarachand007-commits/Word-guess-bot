from bot_common import games, is_game_active, send_main_menu
from multi_games import (
    new_sudoku_game,
    sudoku_move,
    new_ttt_game,
    join_ttt_game,
    ttt_move,
)
from multi_games_ui import sudoku_text, sudoku_keyboard, ttt_text, ttt_keyboard, main_menu_keyboard


async def start_sudoku(chat_id, user, context):
    if is_game_active(chat_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="A game is already active in this chat. Finish it first.",
        )
        return

    games[chat_id] = new_sudoku_game(user.id)
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=sudoku_text(games[chat_id]),
        reply_markup=sudoku_keyboard(),
    )
    games[chat_id]["message_id"] = message.message_id


async def start_ttt(chat_id, user, context):
    if is_game_active(chat_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="A game is already active in this chat. Finish it first.",
        )
        return

    games[chat_id] = new_ttt_game(user.id, user.full_name)
    await context.bot.send_message(
        chat_id=chat_id,
        text=ttt_text(games[chat_id]),
        reply_markup=ttt_keyboard(games[chat_id]),
    )


async def handle_multi_game_callback(query, context):
    chat_id = query.message.chat_id
    data = query.data
    user = query.from_user
    game = games.get(chat_id)

    if data == "menu_sudoku":
        await query.answer()
        await start_sudoku(chat_id, user, context)
        return

    if data == "menu_ttt":
        await query.answer()
        await start_ttt(chat_id, user, context)
        return

    if data == "game_cancel":
        if not game or game.get("status") not in ("playing", "waiting"):
            await query.answer("There is no active game.", show_alert=True)
            return
        if game.get("type") == "sudoku" and user.id != game["owner"]:
            await query.answer("Only the player who started Sudoku can cancel it.", show_alert=True)
            return
        if game.get("type") == "tictactoe" and user.id not in (game.get("x"), game.get("o")):
            await query.answer("Only the players can cancel this game.", show_alert=True)
            return
        games[chat_id]["status"] = "finished"
        await query.answer("Game cancelled.")
        await query.edit_message_text(
            "Game cancelled.",
            reply_markup=None,
        )
        await send_main_menu(chat_id, context)
        return

    if data == "ttt_join":
        if not game or game.get("type") != "tictactoe":
            await query.answer("No Tic Tac Toe game is waiting.", show_alert=True)
            return

        result = join_ttt_game(game, user.id, user.full_name)
        if result == "same_player":
            await query.answer("A different player must join as O.", show_alert=True)
            return
        if result != "joined":
            await query.answer("This game has already started.", show_alert=True)
            return

        await query.answer("You joined as O!")
        await query.edit_message_text(
            ttt_text(game),
            reply_markup=ttt_keyboard(game),
        )
        return

    if data.startswith("ttt_move_"):
        if not game or game.get("type") != "tictactoe":
            await query.answer("No active Tic Tac Toe game.", show_alert=True)
            return

        try:
            cell = int(data.rsplit("_", 1)[1])
        except ValueError:
            await query.answer("Invalid move.", show_alert=True)
            return

        result = ttt_move(game, user.id, cell)

        messages = {
            "not_playing": "This game is not active.",
            "occupied": "That cell is already occupied.",
            "not_your_turn": "It is not your turn.",
            "invalid": "Invalid cell.",
        }

        if result in messages:
            await query.answer(messages[result], show_alert=True)
            return

        await query.answer()

        if result == "won":
            await query.edit_message_text(
                ttt_text(game),
                reply_markup=ttt_keyboard(game),
            )
            return

        if result == "draw":
            await query.edit_message_text(
                ttt_text(game),
                reply_markup=ttt_keyboard(game),
            )
            return

        await query.edit_message_text(
            ttt_text(game),
            reply_markup=ttt_keyboard(game),
        )
        return

    if data == "main_menu":
        if is_game_active(chat_id):
            await query.answer("Finish or cancel the active game first.", show_alert=True)
            return
        await query.answer()
        await send_main_menu(chat_id, context)
        return


async def handle_sudoku_text(update, context):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)

    if not game or game.get("type") != "sudoku" or game.get("status") != "playing":
        return

    parts = update.message.text.strip().split()
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        await update.message.reply_text(
            "Enter your move as: row column number\\nExample: 1 3 4"
        )
        return

    row, col, number = map(int, parts)
    result = sudoku_move(game, update.effective_user.id, row, col, number)

    messages = {
        "not_owner": "Only the player who started Sudoku can make moves.",
        "invalid": "Use row, column and number values from 1 to 9.",
        "fixed": "That cell is part of the original puzzle.",
        "occupied": "That cell is already filled.",
        "wrong": "That number is not correct. Try again.",
        "ended": "This Sudoku game has ended.",
    }

    if result in messages:
        await update.message.reply_text(messages[result])
        return

    if result == "won":
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["message_id"],
            text="Congratulations! You completed Sudoku.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=game["message_id"],
        text=sudoku_text(game),
        reply_markup=sudoku_keyboard(),
    )
