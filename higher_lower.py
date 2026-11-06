import random

MIN_NUMBER = 1
MAX_NUMBER = 500


def new_higher_lower_game():
    return {
        "type": "higher_lower",
        "status": "playing",
        "secret": random.randint(MIN_NUMBER, MAX_NUMBER),
        "attempts": {},
        "winner": None,
        "reward": 0,
    }


def higher_lower_guess(game, user_id, guess):
    if game.get("status") != "playing":
        return "ended"

    if not isinstance(guess, int) or not MIN_NUMBER <= guess <= MAX_NUMBER:
        return "invalid"

    game["attempts"][user_id] = game["attempts"].get(user_id, 0) + 1

    if guess == game["secret"]:
        attempts = game["attempts"][user_id]
        game["winner"] = user_id
        game["status"] = "finished"
        game["reward"] = max(5, 100 - (attempts - 1) * 5)
        return "won"

    if guess < game["secret"]:
        return "higher"

    return "lower"
