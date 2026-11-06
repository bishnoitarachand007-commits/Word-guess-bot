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

        con.execute("""
            CREATE TABLE IF NOT EXISTS higher_lower_players (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                diamonds INTEGER NOT NULL DEFAULT 0
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS higher_lower_group_players (
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
            SELECT user_id, name, diamonds
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
            SELECT user_id, name, diamonds
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


def add_higher_lower_diamonds(user_id, name, amount):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO higher_lower_players (user_id, name, diamonds)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                diamonds = higher_lower_players.diamonds + excluded.diamonds
        """, (user_id, name, amount))


def get_higher_lower_top(limit=10):
    with sqlite3.connect(DB_NAME) as con:
        return con.execute("""
            SELECT user_id, name, diamonds
            FROM higher_lower_players
            ORDER BY diamonds DESC, name ASC
            LIMIT ?
        """, (limit,)).fetchall()


def add_higher_lower_group_diamonds(group_id, user_id, name, amount):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO higher_lower_group_players
                (group_id, user_id, name, diamonds)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(group_id, user_id) DO UPDATE SET
                name = excluded.name,
                diamonds = higher_lower_group_players.diamonds + excluded.diamonds
        """, (group_id, user_id, name, amount))


def get_higher_lower_group_top(group_id, limit=10):
    with sqlite3.connect(DB_NAME) as con:
        return con.execute("""
            SELECT user_id, name, diamonds
            FROM higher_lower_group_players
            WHERE group_id = ?
            ORDER BY diamonds DESC, name ASC
            LIMIT ?
        """, (group_id, limit)).fetchall()


def _get_profile_stats(table, user_id, group_id=None):
    allowed_tables = {
        "players",
        "group_players",
        "higher_lower_players",
        "higher_lower_group_players",
    }
    if table not in allowed_tables:
        raise ValueError("Invalid profile table")

    with sqlite3.connect(DB_NAME) as con:
        if group_id is None:
            row = con.execute(
                f"SELECT user_id, name, diamonds FROM {table} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            rank = con.execute(
                f"""SELECT COUNT(*) + 1 FROM {table}
                    WHERE diamonds > ?
                    OR (diamonds = ? AND name < ?)""",
                (row[2], row[2], row[1]),
            ).fetchone()[0]
        else:
            row = con.execute(
                f"""SELECT user_id, name, diamonds FROM {table}
                    WHERE group_id = ? AND user_id = ?""",
                (group_id, user_id),
            ).fetchone()
            if row is None:
                return None
            rank = con.execute(
                f"""SELECT COUNT(*) + 1 FROM {table}
                    WHERE group_id = ?
                    AND (diamonds > ? OR (diamonds = ? AND name < ?))""",
                (group_id, row[2], row[2], row[1]),
            ).fetchone()[0]

    return {"user_id": row[0], "name": row[1], "diamonds": row[2], "rank": rank}


def get_wordle_profile(user_id):
    return _get_profile_stats("players", user_id)


def get_wordle_group_profile(group_id, user_id):
    return _get_profile_stats("group_players", user_id, group_id)


def get_higher_lower_profile(user_id):
    return _get_profile_stats("higher_lower_players", user_id)


def get_higher_lower_group_profile(group_id, user_id):
    return _get_profile_stats("higher_lower_group_players", user_id, group_id)
