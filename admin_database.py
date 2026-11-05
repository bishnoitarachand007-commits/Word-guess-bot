import sqlite3
from datetime import datetime, timezone

DB_NAME = "leaderboard.db"


def init_admin_db():
    with sqlite3.connect(DB_NAME) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bot_chats (
            chat_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            chat_type TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS bot_admins (
            user_id INTEGER PRIMARY KEY,
            promoted_by INTEGER NOT NULL,
            promoted_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS broadcasts (
            broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            broadcast_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            total_sent INTEGER NOT NULL DEFAULT 0,
            total_failed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS broadcast_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            FOREIGN KEY (broadcast_id) REFERENCES broadcasts(broadcast_id)
        );
        """)


def _now():
    return datetime.now(timezone.utc).isoformat()


def record_user(user_id, name):
    now = _now()
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO bot_users (user_id, name, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                last_seen = excluded.last_seen
        """, (user_id, name, now, now))


def record_chat(chat_id, title, chat_type):
    now = _now()
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO bot_chats
                (chat_id, title, chat_type, first_seen, last_seen, active)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                chat_type = excluded.chat_type,
                last_seen = excluded.last_seen,
                active = 1
        """, (chat_id, title, chat_type, now, now))


def set_admin(user_id, promoted_by):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO bot_admins (user_id, promoted_by, promoted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                promoted_by = excluded.promoted_by,
                promoted_at = excluded.promoted_at
        """, (user_id, promoted_by, _now()))


def remove_admin(user_id):
    with sqlite3.connect(DB_NAME) as con:
        cur = con.execute(
            "DELETE FROM bot_admins WHERE user_id = ?", (user_id,)
        )
        return cur.rowcount > 0


def is_admin(user_id):
    with sqlite3.connect(DB_NAME) as con:
        return con.execute(
            "SELECT 1 FROM bot_admins WHERE user_id = ?", (user_id,)
        ).fetchone() is not None


def get_stats():
    today = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(DB_NAME) as con:
        users = con.execute(
            "SELECT COUNT(*) FROM bot_users WHERE blocked = 0"
        ).fetchone()[0]
        daily = con.execute(
            "SELECT COUNT(*) FROM bot_users WHERE substr(last_seen, 1, 10) = ?",
            (today,)
        ).fetchone()[0]
        groups = con.execute(
            "SELECT COUNT(*) FROM bot_chats WHERE chat_type IN ('group', 'supergroup') AND active = 1"
        ).fetchone()[0]
        admins = con.execute(
            "SELECT COUNT(*) FROM bot_admins"
        ).fetchone()[0]
    return {"users": users, "daily_users": daily, "groups": groups, "admins": admins}


def create_broadcast(sender_id, broadcast_type):
    with sqlite3.connect(DB_NAME) as con:
        cur = con.execute(
            "INSERT INTO broadcasts (sender_id, broadcast_type, created_at) VALUES (?, ?, ?)",
            (sender_id, broadcast_type, _now())
        )
        return cur.lastrowid


def save_broadcast_message(broadcast_id, chat_id, message_id):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO broadcast_messages (broadcast_id, chat_id, message_id)
            VALUES (?, ?, ?)
        """, (broadcast_id, chat_id, message_id))


def finish_broadcast(broadcast_id, sent, failed):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            UPDATE broadcasts SET total_sent = ?, total_failed = ?
            WHERE broadcast_id = ?
        """, (sent, failed, broadcast_id))


def get_latest_broadcast():
    with sqlite3.connect(DB_NAME) as con:
        row = con.execute("""
            SELECT broadcast_id FROM broadcasts
            ORDER BY broadcast_id DESC LIMIT 1
        """).fetchone()
        if not row:
            return None
        messages = con.execute("""
            SELECT chat_id, message_id FROM broadcast_messages
            WHERE broadcast_id = ?
        """, (row[0],)).fetchall()
    return row[0], messages


def get_broadcast_targets(broadcast_type):
    with sqlite3.connect(DB_NAME) as con:
        if broadcast_type in ("all", "dm"):
            users = con.execute(
                "SELECT user_id FROM bot_users WHERE blocked = 0"
            ).fetchall()
        else:
            users = []

        if broadcast_type in ("all", "chat"):
            chats = con.execute("""
                SELECT chat_id FROM bot_chats
                WHERE chat_type IN ('group', 'supergroup') AND active = 1
            """).fetchall()
        else:
            chats = []

    return [row[0] for row in users], [row[0] for row in chats]


def mark_user_blocked(user_id):
    with sqlite3.connect(DB_NAME) as con:
        con.execute(
            "UPDATE bot_users SET blocked = 1 WHERE user_id = ?",
            (user_id,)
        )


def mark_chat_inactive(chat_id):
    with sqlite3.connect(DB_NAME) as con:
        con.execute(
            "UPDATE bot_chats SET active = 0 WHERE chat_id = ?",
            (chat_id,)
        )
