from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Wordle", callback_data="menu_wordle", style="success", icon_custom_emoji_id="5298988357538328017")],
        [InlineKeyboardButton("Sudoku", callback_data="menu_sudoku", style="primary", icon_custom_emoji_id="5895682417305325765")],
        [InlineKeyboardButton("Tic Tac Toe", callback_data="menu_ttt", style="success", icon_custom_emoji_id="5361741454685256344")],
        [InlineKeyboardButton("BACK", callback_data="intro_back", style="primary", icon_custom_emoji_id="5258236805890710909")],
    ])


def wordle_menu_keyboard(mode):
    mode_label = "IMAGE MODE" if mode == "image" else "NORMAL MODE"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"MODE: {mode_label}",
            callback_data="toggle_mode",
            style="success",
            icon_custom_emoji_id="5258012149036365477",
        )],
        [InlineKeyboardButton(
            "START NEW GAME",
            callback_data="new_game",
            style="primary",
            icon_custom_emoji_id="5258508428212445001",
        )],
        [InlineKeyboardButton(
            "BACK",
            callback_data="main_menu",
            style="primary",
            icon_custom_emoji_id="5258236805890710909",
        )],
    ])


def wordle_finished_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "START NEW GAME",
            callback_data="new_game",
            style="success",
            icon_custom_emoji_id="5258508428212445001",
        )]
    ])


def mode_keyboard(mode):
    return wordle_menu_keyboard(mode)


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
            InlineKeyboardButton("START NEW GAME", callback_data="ttt_restart", style="success", icon_custom_emoji_id="5258508428212445001")
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
