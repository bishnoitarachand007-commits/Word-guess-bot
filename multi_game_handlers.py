import asyncio
import uuid

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
        return

    games[chat_id] = new_sudoku_game(user.id)
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=sudoku_text(games[chat_id]),
        reply_markup=sudoku_keyboard(),
    )
    games[chat_id]["message_id"] = message.message_id


async def ttt_wait_timeout(context, chat_id, message_id, token):
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        return

    game = games.get(chat_id)
    if (
        not game
        or game.get("type") != "tictactoe"
        or game.get("status") != "waiting"
        or game.get("wait_token") != token
    ):
        return

    game["status"] = "ended"
    game["end_reason"] = "join_timeout"
    game["waiting_task"] = None

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=ttt_text(game),
        reply_markup=ttt_keyboard(game),
    )


def cancel_ttt_wait(game):
    task = game.get("waiting_task")
    if task and not task.done():
        task.cancel()
    game["waiting_task"] = None


async def start_ttt(chat_id, user, context):
    if is_game_active(chat_id):
        return

    game = new_ttt_game(user.id, user.full_name)
    game["wait_token"] = uuid.uuid4().hex
    games[chat_id] = game
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=ttt_text(games[chat_id]),
        reply_markup=ttt_keyboard(games[chat_id]),
    )
    games[chat_id]["message_id"] = message.message_id
    game["waiting_task"] = asyncio.create_task(
        ttt_wait_timeout(
            context, chat_id, message.message_id, game["wait_token"]
        )
    )


async def handle_multi_game_callback(query, context):
    chat_id = query.message.chat_id
    data = query.data
    user = query.from_user
    game = games.get(chat_id)

    if data == "menu_sudoku":
        await query.answer()
        await query.edit_message_text(
            "Sudoku is still under maintenance.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "menu_ttt":
        await query.answer()
        await start_ttt(chat_id, user, context)
        return

    if data == "ttt_restart":
        if not game or game.get("type") != "tictactoe" or game.get("status") not in ("finished", "ended"):
            await query.answer()
            return
        cancel_ttt_wait(game)
        new_game = new_ttt_game(user.id, user.full_name)
        new_game["wait_token"] = uuid.uuid4().hex
        new_game["message_id"] = query.message.message_id
        games[chat_id] = new_game
        await query.answer("New game started!")
        await query.edit_message_text(
            ttt_text(new_game),
            reply_markup=ttt_keyboard(new_game),
        )
        new_game["waiting_task"] = asyncio.create_task(
            ttt_wait_timeout(
                context,
                chat_id,
                query.message.message_id,
                new_game["wait_token"],
            )
        )
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

        cancel_ttt_wait(game)
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



async def handle_sudoku_text(update, context):
    return
