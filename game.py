import random

MAX_ATTEMPTS = 20
VISIBLE_ROWS = 8


def load_words():
    with open("words.txt", "r", encoding="utf-8") as file:
        return list(dict.fromkeys(
            word.strip().upper()
            for word in file
            if len(word.strip()) == 5 and word.strip().isalpha()
        ))


def load_answers():
    with open("answers.txt", "r", encoding="utf-8") as file:
        answers = list(dict.fromkeys(
            word.strip().upper()
            for word in file
            if len(word.strip()) == 5 and word.strip().isalpha()
        ))
    if not answers:
        raise ValueError("answers.txt has no valid answers")
    return answers


def new_game():
    return {
        "secret": random.choice(load_answers()),
        "attempts": 0,
        "history": [],
        "guessed_words": [],
        "status": "playing",
        "reward": 0
    }


def check_guess(secret, guess):
    secret = secret.upper()
    guess = guess.upper()

    if len(guess) != 5 or not guess.isalpha():
        return None

    result = ["absent"] * 5
    remaining = list(secret)

    for i in range(5):
        if guess[i] == secret[i]:
            result[i] = "correct"
            remaining[i] = None

    for i in range(5):
        if result[i] == "absent" and guess[i] in remaining:
            result[i] = "present"
            remaining[remaining.index(guess[i])] = None

    return result


def submit_guess(game, guess):
    if game["status"] != "playing":
        return "ended"

    guess = guess.strip().upper()

    if len(guess) != 5 or not guess.isalpha():
        return "invalid"

    guessed_words = game.setdefault(
        "guessed_words",
        [previous for previous, _ in game["history"]],
    )
    if guess in guessed_words:
        return "duplicate"

    feedback = check_guess(game["secret"], guess)
    game["attempts"] += 1
    guessed_words.append(guess)
    game["history"].append((guess, feedback))
    game["history"] = game["history"][-VISIBLE_ROWS:]

    if guess == game["secret"]:
        game["status"] = "won"
        game["reward"] = max(5, 100 - (game["attempts"] - 1) * 5)
        return "won"

    if game["attempts"] >= MAX_ATTEMPTS:
        game["status"] = "lost"
        return "lost"

    return "playing"
