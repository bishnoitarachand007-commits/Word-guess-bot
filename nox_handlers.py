import asyncio
import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
import nox_database
import nox_economy as economy
from nox_game_engine import (
    deal_cards, pass_card, find_winner, computer_choose_card,
    get_computer_bot_names, create_scoreboard, award_round_points,
    get_game_rankings,
)

MAX_PLAYERS = 4
MIN_HUMANS = 2
LOBBY_SECONDS = 180
TURN_SECONDS = 60
OWNER_ID = 8677603281
ACTIVE_GAMES = {}
LOBBY_TASKS = {}
GROUP_LOCKS = {}


def db_connect():
    return sqlite3.connect(nox_database.DB_NAME, timeout=15)


def group_lock(group_id):
    return GROUP_LOCKS.setdefault(group_id, asyncio.Lock())


def is_group(update):
    return bool(update.effective_chat and update.effective_chat.type in
                (ChatType.GROUP, ChatType.SUPERGROUP))


def display_name(user):
    return user.full_name or user.first_name or str(user.id)


def parse_rounds(args):
    rounds = int(args[0]) if args else 1
    if len(args) > 1 or rounds not in (1, 3, 5, 7, 10, 12):
        raise ValueError
    return rounds


def get_waiting_game(group_id):
    db = db_connect()
    try:
        return db.execute(
            "SELECT game_id,total_rounds FROM games "
            "WHERE group_id=? AND status='waiting' ORDER BY game_id DESC LIMIT 1",
            (group_id,)
        ).fetchone()
    finally:
        db.close()


def get_active_group_game(group_id):
    db = db_connect()
    try:
        return db.execute(
            "SELECT game_id FROM games WHERE group_id=? "
            "AND status IN ('waiting','running') LIMIT 1", (group_id,)
        ).fetchone()
    finally:
        db.close()


async def nox_new(update, context):
    await create_lobby(update, context, False)


async def nox_tournament(update, context):
    await create_lobby(update, context, True)


async def create_lobby(update, context, tournament=False):
    if not is_group(update):
        await update.effective_message.reply_text("NOX group mein play hota hai.")
        return
    try:
        rounds = parse_rounds(context.args)
    except (ValueError, TypeError):
        await update.effective_message.reply_text(
            "Usage: /noxnew [1|3|5|7|10|12]"
        )
        return

    chat, user = update.effective_chat, update.effective_user
    async with group_lock(chat.id):
        if get_active_group_game(chat.id):
            await update.effective_message.reply_text("Is group mein NOX game already active hai.")
            return
        name = display_name(user)
        db = db_connect()
        try:
            cur = db.cursor()
            cur.execute(
                "INSERT INTO games(group_id,status,total_rounds) VALUES(?,'waiting',?)",
                (chat.id, rounds)
            )
            game_id = cur.lastrowid
            cur.execute(
                "INSERT OR IGNORE INTO players(user_id,display_name) VALUES(?,?)",
                (user.id, name)
            )
            cur.execute(
                "INSERT INTO game_players(game_id,user_id,points,player_name,is_bot) "
                "VALUES(?,?,0,?,0)", (game_id, user.id, name)
            )
            if tournament:
                cur.execute(
                    "INSERT INTO nox_tournaments"
                    "(game_id,creator_id,prize_pool,reserved_prize,status,created_at) "
                    "VALUES(?,?,0,0,'waiting',?)",
                    (game_id, user.id, datetime.now().astimezone().isoformat())
                )
            db.commit()
        finally:
            db.close()
        LOBBY_TASKS[game_id] = asyncio.create_task(
            auto_start_lobby(context.bot, game_id, chat.id)
        )

    label = "Free NOX tournament" if tournament else "NOX game"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Join", callback_data=f"nox_join:{game_id}")],
        [InlineKeyboardButton("Start now", callback_data=f"nox_hoststart:{game_id}")]
    ])
    await update.effective_message.reply_text(
        f"🃏 {label} #{game_id}\nHost: {name}\nRounds: {rounds}\n"
        f"Players: 1/{MAX_PLAYERS}\nMinimum {MIN_HUMANS} humans. "
        f"Auto-start in 3 minutes.",
        reply_markup=keyboard
    )


async def join_lobby(group_id, user, reply):
    waiting = get_waiting_game(group_id)
    if not waiting:
        await reply("Waiting NOX lobby nahi hai. /noxnew use karo.")
        return
    game_id = waiting[0]
    name = display_name(user)
    db = db_connect()
    try:
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM game_players WHERE game_id=?", (game_id,))
        count = cur.fetchone()[0]
        cur.execute(
            "SELECT 1 FROM game_players WHERE game_id=? AND user_id=?",
            (game_id, user.id)
        )
        if cur.fetchone():
            await reply("Tum already lobby mein ho.")
            return
        if count >= MAX_PLAYERS:
            await reply("Lobby full hai.")
            return
        cur.execute(
            "INSERT OR IGNORE INTO players(user_id,display_name) VALUES(?,?)",
            (user.id, name)
        )
        cur.execute(
            "INSERT INTO game_players(game_id,user_id,points,player_name,is_bot) "
            "VALUES(?,?,0,?,0)", (game_id, user.id, name)
        )
        db.commit()
    finally:
        db.close()
    economy.register_group_player(group_id, user.id, name)
    await reply(f"✅ {name} joined ({count + 1}/{MAX_PLAYERS}).")


async def nox_join(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group mein use karo.")
        return
    await join_lobby(update.effective_chat.id, update.effective_user,
                     update.effective_message.reply_text)


async def nox_leave(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group mein use karo.")
        return
    waiting = get_waiting_game(update.effective_chat.id)
    if not waiting:
        await update.effective_message.reply_text("Waiting lobby nahi hai.")
        return
    db = db_connect()
    try:
        cur = db.cursor()
        cur.execute(
            "DELETE FROM game_players WHERE game_id=? AND user_id=?",
            (waiting[0], update.effective_user.id)
        )
        removed = cur.rowcount
        db.commit()
    finally:
        db.close()
    await update.effective_message.reply_text(
        "Lobby se leave kar diya." if removed else "Tum lobby mein nahi ho."
    )


async def nox_start_game(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group mein use karo.")
        return
    waiting = get_waiting_game(update.effective_chat.id)
    if not waiting:
        await update.effective_message.reply_text("Waiting lobby nahi hai.")
        return
    db = db_connect()
    try:
        host = db.execute(
            "SELECT user_id FROM game_players WHERE game_id=? AND is_bot=0 "
            "ORDER BY id LIMIT 1", (waiting[0],)
        ).fetchone()
    finally:
        db.close()
    user = update.effective_user
    is_admin = False
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception:
        pass
    if (not host or host[0] != user.id) and not is_admin:
        await update.effective_message.reply_text("Sirf host ya group admin start kar sakta hai.")
        return
    await start_lobby(context.bot, waiting[0], update.effective_chat.id)


async def auto_start_lobby(bot, game_id, group_id):
    try:
        await asyncio.sleep(LOBBY_SECONDS)
        await start_lobby(bot, game_id, group_id)
    except asyncio.CancelledError:
        pass
    finally:
        LOBBY_TASKS.pop(game_id, None)


async def start_lobby(bot, game_id, group_id):
    async with group_lock(group_id):
        if game_id in ACTIVE_GAMES:
            return
        db = db_connect()
        try:
            cur = db.cursor()
            cur.execute(
                "SELECT status,total_rounds FROM games WHERE game_id=? AND group_id=?",
                (game_id, group_id)
            )
            row = cur.fetchone()
            if not row or row[0] != "waiting":
                return
            cur.execute(
                "SELECT user_id,player_name,is_bot FROM game_players "
                "WHERE game_id=? ORDER BY id", (game_id,)
            )
            rows = cur.fetchall()
            humans = [r for r in rows if not r[2]]
            if len(humans) < MIN_HUMANS:
                cur.execute("UPDATE games SET status='cancelled' WHERE game_id=?", (game_id,))
                cur.execute("UPDATE nox_tournaments SET status='cancelled' WHERE game_id=?", (game_id,))
                db.commit()
                await bot.send_message(group_id, "NOX lobby cancelled: minimum 2 human players required.")
                return
            names = [r[1] for r in rows]
            bot_names = get_computer_bot_names(MAX_PLAYERS - len(rows))
            for bot_name in bot_names:
                cur.execute(
                    "INSERT INTO game_players(game_id,user_id,points,player_name,is_bot) "
                    "VALUES(?,0,0,?,1)", (game_id, bot_name)
                )
                names.append(bot_name)
            cur.execute("UPDATE games SET status='running' WHERE game_id=?", (game_id,))
            cur.execute(
                "UPDATE nox_tournaments SET status='running' "
                "WHERE game_id=? AND status='waiting'", (game_id,)
            )
            db.commit()
        finally:
            db.close()

        hands = deal_cards(len(names))
        ACTIVE_GAMES[game_id] = {
            "group_id": group_id, "names": names, "hands": hands,
            "scoreboard": create_scoreboard(names), "round": 1,
            "total_rounds": row[1], "current": 0, "turn_id": 0,
            "turn_active": False, "turn_task": None,
            "user_ids": [r[0] for r in rows] + [0] * len(bot_names),
            "is_tournament": bool(
                db_value(game_id, "SELECT 1 FROM nox_tournaments WHERE game_id=?")
            )
        }
        await bot.send_message(
            group_id,
            f"🃏 NOX game #{game_id} started!\n"
            + "\n".join(f"{i+1}. {name}" for i, name in enumerate(names))
        )
        await start_turn(bot, game_id)


def db_value(game_id, query):
    db = db_connect()
    try:
        return db.execute(query, (game_id,)).fetchone()
    finally:
        db.close()


async def start_turn(bot, game_id):
    game = ACTIVE_GAMES.get(game_id)
    if not game:
        return
    for _ in range(len(game["names"])):
        index = game["current"]
        if game["user_ids"][index] == 0:
            card_index = computer_choose_card(game["hands"][index])
            await process_card_pass(bot, game_id, index, card_index, continue_turn=False)
            if game_id not in ACTIVE_GAMES:
                return
            continue
        game["turn_id"] += 1
        game["turn_active"] = True
        turn_id = game["turn_id"]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Open private cards",
                callback_data=f"nox_turn:{game_id}:{turn_id}"
            )
        ]])
        try:
            await bot.send_message(
                game["group_id"],
                f"🎴 {game['names'][index]}'s turn. Choose a card in private chat.",
                reply_markup=keyboard
            )
        except Exception:
            game["turn_active"] = False
            game["current"] = (index + 1) % len(game["names"])
            continue
        game["turn_task"] = asyncio.create_task(
            turn_timeout(bot, game_id, turn_id)
        )
        return
    await end_game(bot, game_id, "Turn cycle ended.")


async def turn_timeout(bot, game_id, turn_id):
    try:
        await asyncio.sleep(TURN_SECONDS)
        game = ACTIVE_GAMES.get(game_id)
        if not game or not game["turn_active"] or game["turn_id"] != turn_id:
            return
        index = game["current"]
        await process_card_pass(
            bot, game_id, index, computer_choose_card(game["hands"][index])
        )
    except asyncio.CancelledError:
        pass


async def nox_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    parts = data.split(":")
    try:
        action, game_id = parts[0], int(parts[1])
    except (ValueError, IndexError):
        await query.answer("Invalid NOX action.", show_alert=True)
        return
    game = ACTIVE_GAMES.get(game_id)

    if action == "nox_join":
        await query.answer()
        if query.message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return
        await join_lobby(query.message.chat_id, query.from_user,
                         query.message.reply_text)
        return
    if action == "nox_hoststart":
        await query.answer()
        waiting = get_waiting_game(query.message.chat_id)
        if waiting:
            fake = type("Obj", (), {
                "effective_chat": query.message.chat,
                "effective_user": query.from_user,
                "effective_message": query.message
            })()
            await nox_start_game(fake, context)
        return
    if not game:
        await query.answer("Game not active.", show_alert=True)
        return

    if action == "nox_turn":
        if len(parts) != 3:
            await query.answer("Invalid turn.", show_alert=True)
            return
        turn_id = int(parts[2])
        if not game["turn_active"] or turn_id != game["turn_id"]:
            await query.answer("Turn expired.", show_alert=True)
            return
        index = game["current"]
        if game["user_ids"][index] != query.from_user.id:
            await query.answer("Ye tumhara turn nahi hai.", show_alert=True)
            return
        cards = game["hands"][index]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"{card['rank']} {card['suit']}",
                callback_data=f"nox_card:{game_id}:{turn_id}:{i}"
            )] for i, card in enumerate(cards)
        ])
        try:
            await context.bot.send_message(
                query.from_user.id, "Apna ek card choose karo:", reply_markup=keyboard
            )
            await query.answer("Private chat check karo.")
        except Exception:
            await query.answer("Pehle bot ko private /start bhejo.", show_alert=True)
        return

    if action == "nox_card":
        if len(parts) != 4:
            await query.answer("Invalid card.", show_alert=True)
            return
        turn_id, card_index = int(parts[2]), int(parts[3])
        index = game["current"]
        if (not game["turn_active"] or turn_id != game["turn_id"]
                or game["user_ids"][index] != query.from_user.id
                or not 0 <= card_index < len(game["hands"][index])):
            await query.answer("Turn ya card invalid hai.", show_alert=True)
            return
        await query.answer("Card passed!")
        if game.get("turn_task"):
            game["turn_task"].cancel()
        game["turn_active"] = False
        await process_card_pass(context.bot, game_id, index, card_index)


async def process_card_pass(bot, game_id, sender, card_index, continue_turn=True):
    game = ACTIVE_GAMES.get(game_id)
    if not game or not 0 <= sender < len(game["hands"]):
        return
    if not 0 <= card_index < len(game["hands"][sender]):
        return
    receiver, card = pass_card(game["hands"], sender, card_index)
    await bot.send_message(
        game["group_id"],
        f"➡️ {game['names'][sender]} passed a card to {game['names'][receiver]}."
    )
    winner = find_winner(game["hands"])
    if winner:
        winner_index = winner["player"]
        winner_name = game["names"][winner_index]
        points = award_round_points(game["scoreboard"], winner_name, winner)
        db = db_connect()
        try:
            db.execute(
                "UPDATE game_players SET points=points+? "
                "WHERE game_id=? AND player_name=?",
                (points, game_id, winner_name)
            )
            db.commit()
        finally:
            db.close()
        await bot.send_message(
            game["group_id"],
            f"🏆 Round {game['round']} winner: {winner_name}\n"
            f"Rank: {winner['rank']} | +{points} points"
        )
        if game["round"] >= game["total_rounds"]:
            await end_game(bot, game_id)
            return
        game["round"] += 1
        game["hands"] = deal_cards(len(game["names"]))
        game["current"] = 0
        await bot.send_message(
            game["group_id"], f"Next round: {game['round']}/{game['total_rounds']}"
        )
    else:
        game["current"] = receiver
    if continue_turn and game_id in ACTIVE_GAMES:
        await start_turn(bot, game_id)


async def end_game(bot, game_id, reason=None):
    game = ACTIVE_GAMES.pop(game_id, None)
    if not game:
        return
    if game.get("turn_task"):
        game["turn_task"].cancel()
    rankings = get_game_rankings(game["scoreboard"])
    text = "🏁 NOX game finished!\n"
    if reason:
        text += reason + "\n"
    text += "\n".join(
        f"{i+1}. {name} — {score} points"
        for i, (name, score) in enumerate(rankings)
    )
    db = db_connect()
    try:
        db.execute("UPDATE games SET status='finished' WHERE game_id=?", (game_id,))
        db.execute(
            "UPDATE nox_tournaments SET status='finished',reserved_prize=0 "
            "WHERE game_id=? AND status='running'", (game_id,)
        )
        db.commit()
    finally:
        db.close()
    await bot.send_message(game["group_id"], text)


async def nox_game_end(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group mein use karo.")
        return
    game_id = get_active_group_game(update.effective_chat.id)
    if not game_id:
        await update.effective_message.reply_text("Active NOX game nahi hai.")
        return
    user = update.effective_user
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            await update.effective_message.reply_text("Group admin only.")
            return
    except Exception:
        await update.effective_message.reply_text("Admin permission verify nahi hui.")
        return
    active = ACTIVE_GAMES.get(game_id[0])
    if active and active.get("turn_task"):
        active["turn_task"].cancel()
    ACTIVE_GAMES.pop(game_id[0], None)
    task = LOBBY_TASKS.pop(game_id[0], None)
    if task:
        task.cancel()
    db = db_connect()
    try:
        db.execute(
            "UPDATE games SET status='cancelled' WHERE game_id=? "
            "AND status IN ('waiting','running')", (game_id[0],)
        )
        db.execute(
            "UPDATE nox_tournaments SET status='cancelled',reserved_prize=0 "
            "WHERE game_id=? AND status IN ('waiting','running')", (game_id[0],)
        )
        db.commit()
    finally:
        db.close()
    await update.effective_message.reply_text("NOX game ended by group admin.")


async def nox_cancel(update, context):
    await nox_game_end(update, context)


async def nox_wallet(update, context):
    user = update.effective_user
    try:
        row = economy.wallet_summary(user.id, display_name(user))
        await update.effective_message.reply_text(
            f"💎 NOX Wallet — {display_name(user)}\n"
            f"Balance: {row[0]:,} NOX\n"
            f"Total earned: {row[1]:,}\n"
            f"Tournament winnings: {row[2]:,}\n"
            f"Daily earned: {row[3]:,}\n"
            f"Total transferred: {row[4]:,}"
        )
    except Exception:
        await update.effective_message.reply_text("Wallet abhi load nahi ho paaya.")


async def nox_pay(update, context):
    message = update.effective_message
    user = update.effective_user
    if not is_group(update) or not message.reply_to_message:
        await message.reply_text("Kisi member ke message par reply karke /noxpay 500 use karo.")
        return
    if not context.args or not context.args[0].isdigit():
        await message.reply_text("Usage: reply karke /noxpay 500")
        return
    receiver = message.reply_to_message.from_user
    if receiver.is_bot:
        await message.reply_text("Bot ko NOX transfer nahi kar sakte.")
        return
    try:
        amount = int(context.args[0])
        received, tax = economy.transfer_nox(
            user.id, display_name(user), receiver.id, display_name(receiver), amount
        )
        economy.register_group_player(update.effective_chat.id, user.id, display_name(user))
        economy.register_group_player(update.effective_chat.id, receiver.id, display_name(receiver))
        await message.reply_text(
            f"✅ Transfer complete\n{amount:,} NOX sent\n"
            f"{received:,} NOX received by {display_name(receiver)}\n"
            f"Fee: {tax:,} NOX"
        )
    except (ValueError, TypeError) as exc:
        await message.reply_text(str(exc))
    except Exception:
        await message.reply_text("Transfer complete nahi hua. Dobara try karo.")


async def nox_daily(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Daily NOX claim group mein hota hai.")
        return
    user = update.effective_user
    try:
        reward = economy.claim_daily_nox(
            user.id, display_name(user), update.effective_chat.id
        )
        economy.register_group_player(
            update.effective_chat.id, user.id, display_name(user)
        )
        await update.effective_message.reply_text(
            f"🎁 {display_name(user)} ko {reward:,} NOX daily reward mila!"
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
    except Exception:
        await update.effective_message.reply_text("Daily claim abhi complete nahi hua.")


async def nox_claim(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group claim group mein hota hai.")
        return
    try:
        chat = await context.bot.get_chat(update.effective_chat.id)
        if (chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
                and (getattr(chat, "members_count", 0) or 0) < 30):
            await update.effective_message.reply_text(
                "Group claim ke liye kam se kam 30 members chahiye."
            )
            return
        user = update.effective_user
        reward = economy.claim_group_nox(
            user.id, display_name(user), update.effective_chat.id
        )
        economy.register_group_player(
            update.effective_chat.id, user.id, display_name(user)
        )
        await update.effective_message.reply_text(
            f"🎉 {display_name(user)} claimed {reward:,} NOX for this group!"
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
    except Exception:
        await update.effective_message.reply_text("Group claim abhi complete nahi hua.")


async def nox_toprich(update, context):
    if not is_group(update):
        await update.effective_message.reply_text("Group ranking group mein dekho.")
        return
    db = db_connect()
    try:
        rows = db.execute("""
            SELECT gp.display_name, COALESCE(w.nox_balance,0)
            FROM nox_group_players gp
            LEFT JOIN wallets w ON w.user_id=gp.user_id
            WHERE gp.group_id=?
            ORDER BY COALESCE(w.nox_balance,0) DESC
            LIMIT 10
        """, (update.effective_chat.id,)).fetchall()
    finally:
        db.close()
    if not rows:
        await update.effective_message.reply_text("Abhi group NOX ranking empty hai.")
        return
    text = "🏆 Group NOX Rich Ranking\n"
    text += "\n".join(
        f"{i}. {name}: {balance:,} NOX"
        for i, (name, balance) in enumerate(rows, 1)
    )
    await update.effective_message.reply_text(text)


async def nox_globaltoprich(update, context):
    db = db_connect()
    try:
        rows = db.execute("""
            SELECT p.display_name, w.nox_balance
            FROM wallets w JOIN players p ON p.user_id=w.user_id
            ORDER BY w.nox_balance DESC LIMIT 10
        """).fetchall()
    finally:
        db.close()
    if not rows:
        await update.effective_message.reply_text("Global NOX ranking empty hai.")
        return
    text = "🌍 Global NOX Rich Ranking\n"
    text += "\n".join(
        f"{i}. {name}: {balance:,} NOX"
        for i, (name, balance) in enumerate(rows, 1)
    )
    await update.effective_message.reply_text(text)


async def nox_stats(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("Owner only command.")
        return
    stats = economy.get_economy_stats()
    db = db_connect()
    try:
        season = db.execute(
            "SELECT season_number FROM nox_season WHERE id=1"
        ).fetchone()[0]
        players = db.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
        balance = db.execute(
            "SELECT COALESCE(SUM(nox_balance),0) FROM wallets"
        ).fetchone()[0]
    finally:
        db.close()
    await update.effective_message.reply_text(
        f"📊 NOX Economy — Season {season}\n"
        f"Players: {players}\nCirculating balance: {balance:,}\n"
        f"Burned: {stats[0]:,}\nIssued: {stats[1]:,}\n"
        f"Transferred: {stats[2]:,}"
    )


async def nox_reset(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("Owner only command.")
        return
    if context.args != ["confirm"]:
        await update.effective_message.reply_text(
            "⚠️ NOX season reset sab NOX balances, claims aur season stats zero karega.\n"
            "Confirm karne ke liye /noxreset confirm"
        )
        return
    db = db_connect()
    try:
        active = db.execute(
            "SELECT COUNT(*) FROM games WHERE status IN ('waiting','running')"
        ).fetchone()[0]
    finally:
        db.close()
    if active or ACTIVE_GAMES:
        await update.effective_message.reply_text(
            "Reset blocked: pehle active NOX games finish/cancel karo."
        )
        return
    season = economy.reset_nox_season()
    await update.effective_message.reply_text(
        f"NOX season reset complete. New season: {season}"
    )
