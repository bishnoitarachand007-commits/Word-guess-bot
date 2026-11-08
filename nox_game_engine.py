import random
from collections import Counter

SUITS = ["♥", "♣", "♦", "♠"]
RANKS = ["A", "K", "Q", "J"]

POINTS = {
    "A": 1000,
    "K": 800,
    "Q": 500,
    "J": 300
}


def create_deck():
    deck = [
        {"rank": rank, "suit": suit}
        for suit in SUITS
        for rank in RANKS
    ]
    random.shuffle(deck)
    return deck


def deal_cards(player_count):
    if not 2 <= player_count <= 4:
        raise ValueError("Players must be between 2 and 4")

    deck = create_deck()

    return [
        deck[i * 4:(i + 1) * 4]
        for i in range(player_count)
    ]


def pass_card(hands, sender, card_index):
    player_count = len(hands)

    if not 2 <= player_count <= 4:
        raise ValueError("Invalid player count")

    if not 0 <= sender < player_count:
        raise ValueError("Invalid sender")

    if not 0 <= card_index < len(hands[sender]):
        raise ValueError("Invalid card selection")

    card = hands[sender].pop(card_index)
    receiver = (sender + 1) % player_count
    hands[receiver].append(card)

    return receiver, card


def find_winner(hands):
    for player_index, hand in enumerate(hands):
        counts = Counter(card["rank"] for card in hand)

        for rank in RANKS:
            if counts[rank] >= 4:
                return {
                    "player": player_index,
                    "rank": rank,
                    "points": POINTS[rank],
                    "cards": [
                        card for card in hand
                        if card["rank"] == rank
                    ][:4]
                }

    return None


if __name__ == "__main__":
    test_hands = [
        [
            {"rank": "A", "suit": "♥"},
            {"rank": "A", "suit": "♣"},
            {"rank": "A", "suit": "♦"},
            {"rank": "A", "suit": "♠"}
        ],
        [],
        [],
        []
    ]

    winner = find_winner(test_hands)

    if winner:
        print("ROUND WINNER!")
        print("Player:", winner["player"] + 1)
        print("Winning Rank:", winner["rank"])
        print("Winning Cards:", winner["cards"])
        print("Points:", winner["points"])
    else:
        print("No winner yet")


def computer_choose_card(hand):
    """Choose one random card from a computer player's hand."""
    if not hand:
        raise ValueError("Computer hand cannot be empty")
    return random.randrange(len(hand))


def computer_pass_card(hands, sender):
    """Pass exactly one random card to the next player."""
    if not 0 <= sender < len(hands):
        raise ValueError("Invalid sender")

    card_index = computer_choose_card(hands[sender])
    receiver, card = pass_card(hands, sender, card_index)

    return {
        "sender": sender,
        "receiver": receiver,
        "card": card
    }


BOT_NAMES = ["Ultron", "Vision"]


def get_computer_bot_names(bot_count):
    """Assign unique computer names for one game."""
    if not 0 <= bot_count <= len(BOT_NAMES):
        raise ValueError("Bot count must be between 0 and 2")
    return random.sample(BOT_NAMES, bot_count)


def computer_turn(hands, sender):
    """Run one computer turn and check for a round winner."""
    result = computer_pass_card(hands, sender)
    result["winner"] = find_winner(hands)
    return result


def run_computer_turns(hands, start_player=0):
    """Run turns until a four-of-a-kind winner is found."""
    player_count = len(hands)

    if not 2 <= player_count <= 4:
        raise ValueError("Players must be between 2 and 4")

    if not 0 <= start_player < player_count:
        raise ValueError("Invalid starting player")

    winner = find_winner(hands)
    if winner:
        return {"winner": winner, "turns": 0}

    current_player = start_player
    turns = 0

    while turns < 10000:
        computer_turn(hands, current_player)
        turns += 1

        winner = find_winner(hands)
        if winner:
            return {"winner": winner, "turns": turns}

        current_player = (current_player + 1) % player_count

    return {"winner": None, "turns": turns}


def create_scoreboard(player_names):
    """Create a fresh scoreboard for one game."""
    return {name: 0 for name in player_names}


def award_round_points(scoreboard, player_name, winner):
    """Add round points to the winner's game score."""
    if player_name not in scoreboard:
        raise ValueError("Player not found in scoreboard")

    if not winner or winner["rank"] not in POINTS:
        raise ValueError("Invalid round winner")

    points = POINTS[winner["rank"]]
    scoreboard[player_name] += points
    return points


def get_game_rankings(scoreboard):
    """Return players ordered by total points, highest first."""
    return sorted(
        scoreboard.items(),
        key=lambda item: item[1],
        reverse=True
    )
