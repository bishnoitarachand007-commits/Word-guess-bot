import time
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from admin_database import (
    get_stats,
    is_admin,
    set_admin,
    remove_admin,
)

# Permanent Super Creator: Telegram bot ownership se independent.
CREATOR_ID = 8677603281


def is_creator(user_id):
    return user_id == CREATOR_ID


def has_admin_access(user_id):
    return is_creator(user_id) or is_admin(user_id)


def get_target_user(update, context):
    message = update.effective_message

    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    parts = message.text.strip().split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return None

    return None


async def admin_command_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user

    if not message or not user or not message.text:
        return

    command = message.text.strip().split(maxsplit=1)[0].lower()

    if not has_admin_access(user.id):
        return

    if command in ("!sendall", "!senddm", "!sendchat", "!sendf"):
        if not message.reply_to_message:
            await message.reply_text(
                "Broadcast ke liye jis message ko bhejna hai, us par reply karke command bhejo."
            )
            return

        broadcast_type = {
            "!sendall": "all",
            "!senddm": "dm",
            "!sendchat": "chat",
            "!sendf": "all",
        }[command]

        await run_broadcast(update, context, broadcast_type)
        return

    if command == "!delsend":
        from telegram.error import TelegramError
        from admin_database import get_latest_broadcast

        latest = get_latest_broadcast()
        if not latest or not latest[1]:
            await message.reply_text("No saved broadcast messages found.")
            return

        broadcast_id, sent_messages = latest
        deleted = 0
        failed = 0

        for chat_id, message_id in sent_messages:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id,
                )
                deleted += 1
            except TelegramError:
                failed += 1

            await asyncio.sleep(0.05)

        await message.reply_text(
            f"Broadcast #{broadcast_id} deletion finished.\\n"
            f"Deleted: {deleted}\\nFailed: {failed}"
        )
        return

    if command == "!hp":
        started = time.perf_counter()
        await context.bot.get_me()
        ping_ms = round((time.perf_counter() - started) * 1000)

        stats = get_stats()
        role = "Super Creator" if is_creator(user.id) else "Admin"

        await message.reply_text(
            "BOT STATUS\n\n"
            f"Role: {role}\n"
            f"Ping: {ping_ms} ms\n"
            f"Total users: {stats['users']}\n"
            f"Daily active users: {stats['daily_users']}\n"
            f"Active groups: {stats['groups']}\n"
            f"Promoted admins: {stats['admins']}"
        )
        return

    if command in ("!promote", "!demote"):
        if not is_creator(user.id):
            await message.reply_text("Only the Super Creator can promote or demote admins.")
            return

        target_id = get_target_user(update, context)

        if target_id is None:
            await message.reply_text(
                f"Reply to a user's message or use {command} USER_ID."
            )
            return

        if target_id == CREATOR_ID:
            await message.reply_text("The Super Creator's authority cannot be changed.")
            return

        if command == "!promote":
            set_admin(target_id, CREATOR_ID)
            await message.reply_text(f"User {target_id} is now a bot admin.")
        else:
            removed = remove_admin(target_id)
            if removed:
                await message.reply_text(f"Admin access removed from {target_id}.")
            else:
                await message.reply_text("This user is not a promoted admin.")
        return


async def run_broadcast(update, context, broadcast_type):
    from telegram.error import Forbidden, TelegramError
    from admin_database import (
        get_broadcast_targets,
        create_broadcast,
        save_broadcast_message,
        finish_broadcast,
        mark_user_blocked,
        mark_chat_inactive,
    )

    message = update.effective_message
    users, chats = get_broadcast_targets(broadcast_type)
    targets = users + chats

    if not targets:
        await message.reply_text("No eligible recipients found.")
        return

    broadcast_id = create_broadcast(update.effective_user.id, broadcast_type)
    sent = 0
    failed = 0

    for chat_id in targets:
        try:
            copied = await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat_id,
                message_id=message.reply_to_message.message_id,
            )
            save_broadcast_message(broadcast_id, chat_id, copied.message_id)
            sent += 1
        except Forbidden:
            failed += 1
            if chat_id in users:
                mark_user_blocked(chat_id)
            else:
                mark_chat_inactive(chat_id)
        except TelegramError:
            failed += 1

        await asyncio.sleep(0.05)

    finish_broadcast(broadcast_id, sent, failed)
    await message.reply_text(
        f"Broadcast complete.\nDelivered: {sent}\nFailed: {failed}"
    )
