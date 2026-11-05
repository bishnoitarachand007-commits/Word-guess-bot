# Sudoku and Tic Tac Toe logic.
# These games do not use Wordle diamonds or leaderboards.

SUDOKU_PUZZLE = [
    "530070000",
    "600195000",
    "098000060",
    "800060003",
    "400803001",
    "700020006",
    "060000280",
    "000419005",
    "000080079",
]

SUDOKU_SOLUTION = [
    "534678912",
    "672195348",
    "198342567",
    "859761423",
    "426853791",
    "713924856",
    "961537284",
    "287419635",
    "345286179",
]


def new_sudoku_game(user_id):
    return {
        "type": "sudoku",
        "status": "playing",
        "owner": user_id,
        "grid": [[int(n) for n in row] for row in SUDOKU_PUZZLE],
        "solution": [[int(n) for n in row] for row in SUDOKU_SOLUTION],
        "fixed": [[n != "0" for n in row] for row in SUDOKU_PUZZLE],
    }


def sudoku_move(game, user_id, row, col, number):
    if game["status"] != "playing":
        return "ended"
    if user_id != game["owner"]:
        return "not_owner"
    if not (1 <= row <= 9 and 1 <= col <= 9 and 1 <= number <= 9):
        return "invalid"

    r, c = row - 1, col - 1

    if game["fixed"][r][c]:
        return "fixed"
    if game["grid"][r][c] != 0:
        return "occupied"
    if game["solution"][r][c] != number:
        return "wrong"

    game["grid"][r][c] = number

    if all(
        game["grid"][i][j] == game["solution"][i][j]
        for i in range(9) for j in range(9)
    ):
        game["status"] = "finished"
        return "won"

    return "correct"


def new_ttt_game(x_user_id, x_name):
    return {
        "type": "tictactoe",
        "status": "waiting",
        "x": x_user_id,
        "x_name": x_name,
        "o": None,
        "o_name": None,
        "turn": "X",
        "board": [""] * 9,
        "winner": None,
    }


def join_ttt_game(game, user_id, name):
    if game["status"] != "waiting":
        return "started"
    if user_id == game["x"]:
        return "same_player"
    game["o"] = user_id
    game["o_name"] = name
    game["status"] = "playing"
    return "joined"


def ttt_move(game, user_id, cell):
    if game["status"] != "playing":
        return "not_playing"
    if not isinstance(cell, int) or not 0 <= cell <= 8:
        return "invalid"
    if game["board"][cell]:
        return "occupied"

    symbol = game["turn"]
    expected_user = game["x"] if symbol == "X" else game["o"]

    if user_id != expected_user:
        return "not_your_turn"

    game["board"][cell] = symbol

    winning_lines = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )

    for a, b, c in winning_lines:
        if (
            game["board"][a]
            and game["board"][a] == game["board"][b]
            == game["board"][c]
        ):
            game["winner"] = symbol
            game["status"] = "finished"
            return "won"

    if all(game["board"]):
        game["status"] = "finished"
        return "draw"

    game["turn"] = "O" if symbol == "X" else "X"
    return "moved"
