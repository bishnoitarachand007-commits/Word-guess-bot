from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Wordle", callback_data="menu_wordle", style="success")],
        [InlineKeyboardButton("Sudoku", callback_data="menu_sudoku", style="primary")],
        [InlineKeyboardButton("Tic Tac Toe", callback_data="menu_ttt", style="success")],
    ])


def wordle_menu_keyboard(mode):
    mode_label = "Image Mode" if mode == "image" else "Normal Mode"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CHANGE MODE", callback_data="wordle_modes", style="success")],
        [InlineKeyboardButton("START NEW GAME", callback_data="new_game", style="primary")],
        [InlineKeyboardButton(f"Current mode: {mode_label}", callback_data="wordle_modes", style="success")],
        [InlineKeyboardButton("MAIN MENU", callback_data="main_menu", style="primary")],
    ])


def wordle_finished_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("START NEW GAME", callback_data="new_game", style="success")]
    ])


def mode_keyboard(mode):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(("✓ " if mode == "normal" else "") + "Normal Mode", callback_data="mode_normal", style="success"),
            InlineKeyboardButton(("✓ " if mode == "image" else "") + "Image Mode", callback_data="mode_image", style="primary"),
        ],
        [InlineKeyboardButton("BACK", callback_data="menu_wordle", style="success")],
    ])


def sudoku_text(game):
    lines = ["SUDOKU — Fill in the missing numbers", ""]
    for r, row in enumerate(game["grid"]):
        if r in (3, 6):
            lines.append("------+-------+------")
        parts = []
        for c, number in enumerate(row):
            if c in (3, 6):
                parts.append("|")
            parts.append(str(number) if number else ".")
        lines.append(" ".join(parts))
    lines.extend([
        "",
        "Enter a move as: row column number",
        "Example: 1 3 4",
        "Only the player who started Sudoku can make moves.",
    ])
    return "\n".join(lines)


def sudoku_keyboard():
    return InlineKeyboardMarkup([])


def ttt_keyboard(game):
    buttons = []
    if game["status"] == "playing":
        symbols = {"X": "❌", "O": "⭕"}
        for r in range(3):
            row = []
            for c in range(3):
                cell = r * 3 + c
                label = symbols.get(game["board"][cell], "·")
                row.append(InlineKeyboardButton(label, callback_data=f"ttt_move_{cell}"))
            buttons.append(row)
    elif game["status"] == "waiting":
        buttons.append([
            InlineKeyboardButton("JOIN AS O", callback_data="ttt_join", style="success")
        ])
    elif game["status"] == "finished":
        buttons.append([
            InlineKeyboardButton("START NEW GAME", callback_data="ttt_restart", style="success")
        ])
    return InlineKeyboardMarkup(buttons)


def ttt_text(game):
    if game["status"] == "waiting":
        return f"TIC TAC TOE\n\n❌: {game['x_name']}\nWaiting for another player to join as ⭕."
    if game["status"] == "finished":
        if game["winner"]:
            winner_name = game["x_name"] if game["winner"] == "X" else game["o_name"]
            return f"TIC TAC TOE\n\n{winner_name} wins!"
        return "TIC TAC TOE\n\nIt is a draw!"
    turn_name = game["x_name"] if game["turn"] == "X" else game["o_name"]
    symbol = "❌" if game["turn"] == "X" else "⭕"
    return f"TIC TAC TOE\n\n❌: {game['x_name']}\n⭕: {game['o_name']}\n\nTurn: {symbol} — {turn_name}"
