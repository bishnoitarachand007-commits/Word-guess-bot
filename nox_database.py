import sqlite3
from pathlib import Path

DB_NAME = str(Path(__file__).resolve().parent / "cardgame.db")


def create_tables():
    db = sqlite3.connect(DB_NAME)
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        display_name TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        status TEXT DEFAULT 'waiting',
        total_rounds INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER,
        user_id INTEGER,
        points INTEGER DEFAULT 0,
        player_name TEXT,
        is_bot INTEGER DEFAULT 0,
        FOREIGN KEY(game_id) REFERENCES games(game_id),
        FOREIGN KEY(user_id) REFERENCES players(user_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        user_id INTEGER PRIMARY KEY,
        nox_balance INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES players(user_id)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_player_stats (
        user_id INTEGER PRIMARY KEY,
        total_earned INTEGER DEFAULT 0,
        tournament_winnings INTEGER DEFAULT 0,
        daily_earned INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_daily_claims (
        user_id INTEGER PRIMARY KEY,
        claimed_date TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_group_claims (
        group_id INTEGER PRIMARY KEY,
        season_number INTEGER NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_tournaments (
        game_id INTEGER PRIMARY KEY,
        creator_id INTEGER NOT NULL,
        prize_pool INTEGER NOT NULL,
        reserved_prize INTEGER NOT NULL,
        status TEXT DEFAULT 'waiting',
        created_at TEXT,
        FOREIGN KEY(game_id) REFERENCES games(game_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_economy_stats (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_burned INTEGER DEFAULT 0,
        total_issued INTEGER DEFAULT 0,
        total_transferred INTEGER DEFAULT 0,
        total_tournament_prizes INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    INSERT OR IGNORE INTO nox_economy_stats (id) VALUES (1)
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nox_season (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        season_number INTEGER NOT NULL DEFAULT 1
    )
    """)
    cursor.execute("""
    INSERT OR IGNORE INTO nox_season (id, season_number) VALUES (1, 1)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nox_group_players (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id)
        )
    """)

    db.commit()
    db.close()

    print("Database tables created successfully!")


if __name__ == "__main__":
    create_tables()
