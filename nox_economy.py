import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_NAME = str(Path(__file__).resolve().parent / "cardgame.db")
MAIN_GROUP_ID = -1003724858693
IST = timezone(timedelta(hours=5, minutes=30))


def connect():
    return sqlite3.connect(DB_NAME, timeout=15)


def ensure_player(cursor, user_id, display_name):
    cursor.execute(
        "INSERT OR IGNORE INTO players (user_id, display_name) VALUES (?, ?)",
        (user_id, display_name or "Player")
    )
    cursor.execute(
        "UPDATE players SET display_name = ? WHERE user_id = ?",
        (display_name or "Player", user_id)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO wallets (user_id, nox_balance) VALUES (?, 0)",
        (user_id,)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO nox_player_stats (user_id) VALUES (?)",
        (user_id,)
    )


def wallet_summary(user_id, display_name="Player"):
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()
        ensure_player(cur, user_id, display_name)
        cur.execute("""
            SELECT w.nox_balance, s.total_earned,
                   s.tournament_winnings, s.daily_earned, s.total_spent
            FROM wallets w
            JOIN nox_player_stats s ON s.user_id = w.user_id
            WHERE w.user_id = ?
        """, (user_id,))
        result = cur.fetchone()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def transfer_nox(sender_id, sender_name, receiver_id, receiver_name, amount):
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    if sender_id == receiver_id:
        raise ValueError("You cannot pay yourself.")

    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()
        ensure_player(cur, sender_id, sender_name)
        ensure_player(cur, receiver_id, receiver_name)

        cur.execute(
            "SELECT nox_balance FROM wallets WHERE user_id = ?",
            (sender_id,)
        )
        balance = cur.fetchone()[0]
        if balance < amount:
            raise ValueError("Insufficient NOX balance.")

        tax = (amount * 5 + 50) // 100
        received = amount - tax

        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance - ? WHERE user_id = ?",
            (amount, sender_id)
        )
        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
            (received, receiver_id)
        )
        cur.execute(
            "UPDATE nox_player_stats SET total_earned = total_earned + ? WHERE user_id = ?",
            (received, receiver_id)
        )
        cur.execute(
            "UPDATE nox_player_stats SET total_spent = total_spent + ? WHERE user_id = ?",
            (amount, sender_id)
        )
        cur.execute("""
            UPDATE nox_economy_stats
            SET total_burned = total_burned + ?,
                total_transferred = total_transferred + ?
            WHERE id = 1
        """, (tax, amount))

        db.commit()
        return received, tax
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def claim_daily_nox(user_id, display_name, group_id):
    today = datetime.now(IST).date().isoformat()
    reward = 3000 if group_id == MAIN_GROUP_ID else 2000

    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()
        ensure_player(cur, user_id, display_name)

        cur.execute(
            "SELECT claimed_date FROM nox_daily_claims WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        if row and row[0] == today:
            raise ValueError("You have already claimed today's daily reward.")

        cur.execute("""
            INSERT INTO nox_daily_claims (user_id, claimed_date)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET claimed_date = excluded.claimed_date
        """, (user_id, today))
        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
            (reward, user_id)
        )
        cur.execute("""
            UPDATE nox_player_stats
            SET total_earned = total_earned + ?,
                daily_earned = daily_earned + ?
            WHERE user_id = ?
        """, (reward, reward, user_id))
        cur.execute(
            "UPDATE nox_economy_stats SET total_issued = total_issued + ? WHERE id = 1",
            (reward,)
        )

        db.commit()
        return reward
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def claim_group_nox(user_id, display_name, group_id):
    reward = 10000
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()
        ensure_player(cur, user_id, display_name)

        cur.execute("SELECT season_number FROM nox_season WHERE id = 1")
        season = cur.fetchone()[0]

        cur.execute(
            "SELECT season_number FROM nox_group_claims WHERE group_id = ?",
            (group_id,)
        )
        previous = cur.fetchone()
        if previous and previous[0] == season:
            raise ValueError("This group has already claimed its reward this season.")

        cur.execute("""
            INSERT INTO nox_group_claims (group_id, season_number)
            VALUES (?, ?)
            ON CONFLICT(group_id) DO UPDATE
            SET season_number = excluded.season_number
        """, (group_id, season))
        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
            (reward, user_id)
        )
        cur.execute(
            "UPDATE nox_player_stats SET total_earned = total_earned + ? WHERE user_id = ?",
            (reward, user_id)
        )
        cur.execute(
            "UPDATE nox_economy_stats SET total_issued = total_issued + ? WHERE id = 1",
            (reward,)
        )

        db.commit()
        return reward
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_economy_stats():
    db = connect()
    try:
        cur = db.cursor()
        cur.execute("""
            SELECT total_burned, total_issued,
                   total_transferred, total_tournament_prizes
            FROM nox_economy_stats WHERE id = 1
        """)
        return cur.fetchone()
    finally:
        db.close()


def reset_nox_season():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()

        cur.execute("UPDATE wallets SET nox_balance = 0")
        cur.execute("""
            UPDATE nox_player_stats
            SET total_earned = 0, tournament_winnings = 0,
                daily_earned = 0, total_spent = 0
        """)
        cur.execute("DELETE FROM nox_daily_claims")
        cur.execute("DELETE FROM nox_group_claims")
        cur.execute("DELETE FROM nox_group_players")
        cur.execute("DELETE FROM nox_tournaments")
        cur.execute("""
            UPDATE nox_economy_stats
            SET total_burned = 0, total_issued = 0,
                total_transferred = 0, total_tournament_prizes = 0
            WHERE id = 1
        """)
        cur.execute(
            "UPDATE nox_season SET season_number = season_number + 1 WHERE id = 1"
        )

        db.commit()
        return cur.execute(
            "SELECT season_number FROM nox_season WHERE id = 1"
        ).fetchone()[0]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_tournament(game_id, creator_id, creator_name, prize_pool):
    if not 300 <= prize_pool <= 20000:
        raise ValueError("Prize must be between 300 and 20000 NOX.")

    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()
        ensure_player(cur, creator_id, creator_name)

        cur.execute(
            "SELECT nox_balance FROM wallets WHERE user_id = ?",
            (creator_id,)
        )
        balance = cur.fetchone()[0]
        if balance < prize_pool:
            raise ValueError("Insufficient NOX balance for prize reservation.")

        cur.execute(
            "SELECT 1 FROM nox_tournaments WHERE game_id = ?",
            (game_id,)
        )
        if cur.fetchone():
            raise ValueError("Tournament already exists.")

        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance - ? WHERE user_id = ?",
            (prize_pool, creator_id)
        )
        cur.execute(
            "UPDATE nox_player_stats SET total_spent = total_spent + ? WHERE user_id = ?",
            (prize_pool, creator_id)
        )
        cur.execute("""
            INSERT INTO nox_tournaments
            (game_id, creator_id, prize_pool, reserved_prize, status, created_at)
            VALUES (?, ?, ?, ?, 'waiting', ?)
        """, (
            game_id, creator_id, prize_pool, prize_pool,
            datetime.now(IST).isoformat()
        ))

        db.commit()
        return prize_pool
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel_tournament(game_id):
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()

        cur.execute("""
            SELECT creator_id, reserved_prize
            FROM nox_tournaments
            WHERE game_id = ? AND status = 'waiting'
        """, (game_id,))
        tournament = cur.fetchone()
        if not tournament:
            raise ValueError("No cancellable tournament found.")

        creator_id, refund = tournament
        cur.execute(
            "UPDATE games SET status = 'cancelled' "
            "WHERE game_id = ? AND status = 'waiting'",
            (game_id,)
        )
        if cur.rowcount != 1:
            raise ValueError("Tournament game is no longer waiting.")
        cur.execute(
            "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
            (refund, creator_id)
        )
        cur.execute(
            "UPDATE nox_player_stats SET total_spent = MAX(0, total_spent - ?) WHERE user_id = ?",
            (refund, creator_id)
        )
        cur.execute("""
            UPDATE nox_tournaments
            SET status = 'cancelled', reserved_prize = 0
            WHERE game_id = ? AND status = 'waiting'
        """, (game_id,))

        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def settle_tournament(game_id, winners):
    """
    winners: list of dictionaries:
      {"user_id": int, "is_bot": bool, "score": int}

    Only the highest-scoring tied winners should be supplied.
    """
    if not winners:
        raise ValueError("At least one winner is required.")

    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()

        cur.execute("""
            SELECT prize_pool, reserved_prize
            FROM nox_tournaments
            WHERE game_id = ? AND status = 'running'
        """, (game_id,))
        tournament = cur.fetchone()
        if not tournament:
            raise ValueError("Tournament is not in running status.")

        prize_pool, reserved = tournament
        if reserved != prize_pool:
            raise ValueError("Tournament reserve does not match prize pool.")

        highest = max(int(w["score"]) for w in winners)
        winners = [w for w in winners if int(w["score"]) == highest]

        tax = (prize_pool * 10 + 50) // 100
        distributable = prize_pool - tax
        base_share, remainder = divmod(distributable, len(winners))
        rounding_burned = 0

        human_paid = 0
        bot_burned = 0
        winner_payouts = {}

        for index, winner in enumerate(winners):
            amount = base_share + (1 if index < remainder else 0)

            if winner["is_bot"]:
                bot_burned += amount
                continue

            user_id = winner["user_id"]
            cur.execute(
                "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            if cur.rowcount != 1:
                raise ValueError("Human winner wallet is missing.")

            cur.execute("""
                UPDATE nox_player_stats
                SET total_earned = total_earned + ?,
                    tournament_winnings = tournament_winnings + ?
                WHERE user_id = ?
            """, (amount, amount, user_id))
            human_paid += amount
            winner_payouts[str(user_id)] = amount

        total_burned = tax + bot_burned + rounding_burned

        cur.execute("""
            UPDATE nox_economy_stats
            SET total_burned = total_burned + ?,
                total_tournament_prizes = total_tournament_prizes + ?
            WHERE id = 1
        """, (total_burned, prize_pool))

        cur.execute("""
            UPDATE nox_tournaments
            SET status = 'finished', reserved_prize = 0
            WHERE game_id = ? AND status = 'running'
        """, (game_id,))

        db.commit()
        return {
            "prize_pool": prize_pool,
            "tax_burned": tax,
            "bot_share_burned": bot_burned,
            "total_burned": total_burned,
            "rounding_burned": rounding_burned,
            "human_paid": human_paid,
            "winner_share": base_share,
            "winner_payouts": winner_payouts,
            "winner_count": len(winners)
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def register_group_player(group_id, user_id, display_name):
    if user_id <= 0:
        return
    db = connect()
    try:
        db.execute("""
            INSERT INTO nox_group_players (group_id, user_id, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(group_id, user_id)
            DO UPDATE SET display_name = excluded.display_name
        """, (group_id, user_id, display_name or "Player"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def admin_end_tournament(game_id):
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.cursor()

        cur.execute("""
            SELECT creator_id, reserved_prize
            FROM nox_tournaments
            WHERE game_id = ? AND status IN ('waiting', 'running')
        """, (game_id,))
        tournament = cur.fetchone()
        if not tournament:
            raise ValueError("No active tournament found.")

        creator_id, refund = tournament

        cur.execute("""
            UPDATE games SET status = 'cancelled'
            WHERE game_id = ? AND status IN ('waiting', 'running')
        """, (game_id,))
        if cur.rowcount != 1:
            raise ValueError("Game is no longer active.")

        if refund:
            cur.execute(
                "UPDATE wallets SET nox_balance = nox_balance + ? WHERE user_id = ?",
                (refund, creator_id)
            )
            if cur.rowcount != 1:
                raise ValueError("Creator wallet is missing.")
            cur.execute("""
                UPDATE nox_player_stats
                SET total_spent = MAX(0, total_spent - ?)
                WHERE user_id = ?
            """, (refund, creator_id))

        cur.execute("""
            UPDATE nox_tournaments
            SET status = 'cancelled', reserved_prize = 0
            WHERE game_id = ? AND status IN ('waiting', 'running')
        """, (game_id,))
        if cur.rowcount != 1:
            raise ValueError("Tournament state changed.")

        db.commit()
        return refund
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
