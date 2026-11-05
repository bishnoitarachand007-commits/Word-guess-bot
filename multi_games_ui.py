from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Wordle", callback_data="menu_wordle", style="primary")],
        [InlineKeyboardButton("Sudoku", callback_data="menu_sudoku", style="primary")],
        [InlineKeyboardButton("Tic Tac Toe", callback_data="menu_ttt", style="primary")],
    ])


def wordle_menu_keyboard(mode):
    mode_label = "Image Mode" if mode == "image" else "Normal Mode"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CHANGE MODE", callback_data="wordle_modes", style="primary")],
        [InlineKeyboardButton("START NEW GAME", callback_data="new_game", style="primary")],
        [InlineKeyboardButton(f"Current mode: {mode_label}", callback_data="wordle_modes", style="primary")],
        [InlineKeyboardButton("MAIN MENU", callback_data="main_menu", style="primary")],
    ])


def mode_keyboard(mode):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                ("✓ " if mode == "normal" else "") + "Normal Mode",
                callback_data="mode_normal",
                style="primary",
            ),
            InlineKeyboardButton(
                ("✓ " if mode == "image" else "") + "Image Mode",
                callback_data="mode_image",
                style="primary",
            ),
        ],
        [InlineKeyboardButton("BACK", callback_data="menu_wordle", style="primary")],
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CANCEL GAME", callback_data="game_cancel", style="primary")],
        [InlineKeyboardButton("MAIN MENU", callback_data="main_menu", style="primary")],
    ])


def ttt_keyboard(game):
    buttons = []

    if game["status"] == "playing":
        for r in range(3):
            row = []
            for c in range(3):
                cell = r * 3 + c
                label = game["board"][cell] or "·"
                row.append(InlineKeyboardButton(
                    label,
                    callback_data=f"ttt_move_{cell}",
                    style="primary",
                ))
            buttons.append(row)

    if game["status"] == "waiting":
        buttons.append([
            InlineKeyboardButton(
                "JOIN AS O",
                callback_data="ttt_join",
                style="primary",
            )
        ])

    if game["status"] in ("waiting", "playing"):
        buttons.append([
            InlineKeyboardButton(
                "CANCEL GAME",
                callback_data="game_cancel",
                style="primary",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "MAIN MENU",
            callback_data="main_menu",
            style="primary",
        )
    ])

    return InlineKeyboardMarkup(buttons)

def ttt_text(game):
    if game["status"] == "waiting":
        return (
            "TIC TAC TOE\n\n"
            f"X: {game['x_name']}\n"
            "Waiting for another player to join as O."
        )

    if game["status"] == "finished":
        if game["winner"]:
            winner_name = game["x_name"] if game["winner"] == "X" else game["o_name"]
            return f"TIC TAC TOE\n\n{winner_name} wins!"
        return "TIC TAC TOE\n\nIt's a draw!"

    turn_name = game["x_name"] if game["turn"] == "X" else game["o_name"]
    return (
        "TIC TAC TOE\n\n"
        f"X: {game['x_name']}\n"
        f"O: {game['o_name']}\n\n"
        f"Turn: {game['turn']} — {turn_name}"
    )
