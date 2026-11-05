import sqlite3

DB_NAME = "leaderboard.db"


def init_db():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                diamonds INTEGER NOT NULL DEFAULT 0
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS group_players (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                diamonds INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (group_id, user_id)
            )
        """)


def add_diamonds(user_id, name, amount):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO players (user_id, name, diamonds)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                diamonds = players.diamonds + excluded.diamonds
        """, (user_id, name, amount))


def get_top(limit=10):
    with sqlite3.connect(DB_NAME) as con:
        return con.execute("""
            SELECT name, diamonds
            FROM players
            ORDER BY diamonds DESC, name ASC
            LIMIT ?
        """, (limit,)).fetchall()


def add_group_diamonds(group_id, user_id, name, amount):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO group_players (group_id, user_id, name, diamonds)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(group_id, user_id) DO UPDATE SET
                name = excluded.name,
                diamonds = group_players.diamonds + excluded.diamonds
        """, (group_id, user_id, name, amount))


def get_group_top(group_id, limit=10):
    with sqlite3.connect(DB_NAME) as con:
        return con.execute("""
            SELECT name, diamonds
            FROM group_players
            WHERE group_id = ?
            ORDER BY diamonds DESC, name ASC
            LIMIT ?
        """, (group_id, limit)).fetchall()


def get_wordle_mode(chat_id):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                wordle_mode TEXT NOT NULL DEFAULT 'image'
            )
        """)
        row = con.execute(
            "SELECT wordle_mode FROM chat_settings WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()
        return row[0] if row else "image"


def set_wordle_mode(chat_id, mode):
    if mode not in ("image", "normal"):
        raise ValueError("Invalid Wordle mode")
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                wordle_mode TEXT NOT NULL DEFAULT 'image'
            )
        """)
        con.execute("""
            INSERT INTO chat_settings (chat_id, wordle_mode)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                wordle_mode = excluded.wordle_mode
        """, (chat_id, mode))
