# pending.py — uses raw MTProto API instead of get_chat_join_requests()
# Fixes: BOT_METHOD_INVALID on pyrofork 2.3.69

from pyrogram import Client, filters, raw, types
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from RknDeveloper.database import rkn_botz
from RknDeveloper.admin import admin_filter
from RknDeveloper.verify import require_verification
import asyncio


async def _resolve_chat(bot: Client, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply_text(
            "⚠️ Provide a chat ID or username.\n"
            "Usage: `/approve_all -100xxxxxxxxx`\nor `/approve_all @username`"
        )
        return None, None, None
    raw_arg = parts[1]
    try:
        chat = await bot.get_chat(int(raw_arg) if raw_arg.lstrip("-").isdigit() else raw_arg)
        # get InputPeer for raw API calls
        peer = await bot.resolve_peer(chat.id)
        return chat.id, chat.title, peer
    except Exception as e:
        await m.reply_text(f"❌ Could not find chat `{raw_arg}`\nError: `{e}`")
        return None, None, None


async def _raw_approve_all(bot: Client, peer, chat_id: int):
    """
    Uses raw MTProto messages.GetChatInviteImporters to fetch pending requests
    then messages.HideChatJoinRequest to approve each one.
    Works on pyrofork 2.3.69 and TDLib-based forks.
    """
    approved = 0
    offset_date = 0
    offset_user = raw.types.InputUserEmpty()

    while True:
        try:
            result = await bot.invoke(
                raw.functions.messages.GetChatInviteImporters(
                    peer=peer,
                    requested=True,
                    offset_date=offset_date,
                    offset_user=offset_user,
                    limit=100,
                    q=""
                )
            )
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
            continue
        except Exception as e:
            raise e

        importers = result.importers
        if not importers:
            break

        users = {u.id: u for u in result.users}

        for imp in importers:
            try:
                user = users.get(imp.user_id)
                if not user:
                    continue
                input_user = raw.types.InputUser(
                    user_id=user.id,
                    access_hash=user.access_hash
                )
                await bot.invoke(
                    raw.functions.messages.HideChatJoinRequest(
                        peer=peer,
                        user_id=input_user,
                        approved=True
                    )
                )
                approved += 1
                await asyncio.sleep(0.05)  # small delay to avoid flood
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
            except Exception:
                pass

        # paginate
        last = importers[-1]
        offset_date = last.date
        last_user = users.get(last.user_id)
        if last_user:
            offset_user = raw.types.InputUser(
                user_id=last_user.id,
                access_hash=last_user.access_hash
            )
        if len(importers) < 100:
            break

    return approved


async def _raw_decline_all(bot: Client, peer):
    declined = 0
    offset_date = 0
    offset_user = raw.types.InputUserEmpty()

    while True:
        try:
            result = await bot.invoke(
                raw.functions.messages.GetChatInviteImporters(
                    peer=peer,
                    requested=True,
                    offset_date=offset_date,
                    offset_user=offset_user,
                    limit=100,
                    q=""
                )
            )
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
            continue
        except Exception as e:
            raise e

        importers = result.importers
        if not importers:
            break

        users = {u.id: u for u in result.users}

        for imp in importers:
            try:
                user = users.get(imp.user_id)
                if not user:
                    continue
                input_user = raw.types.InputUser(
                    user_id=user.id,
                    access_hash=user.access_hash
                )
                await bot.invoke(
                    raw.functions.messages.HideChatJoinRequest(
                        peer=peer,
                        user_id=input_user,
                        approved=False
                    )
                )
                declined += 1
                await asyncio.sleep(0.05)
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
            except Exception:
                pass

        last = importers[-1]
        offset_date = last.date
        last_user = users.get(last.user_id)
        if last_user:
            offset_user = raw.types.InputUser(
                user_id=last_user.id,
                access_hash=last_user.access_hash
            )
        if len(importers) < 100:
            break

    return declined


async def _raw_count_pending(bot: Client, peer) -> int:
    count = 0
    offset_date = 0
    offset_user = raw.types.InputUserEmpty()

    while True:
        try:
            result = await bot.invoke(
                raw.functions.messages.GetChatInviteImporters(
                    peer=peer,
                    requested=True,
                    offset_date=offset_date,
                    offset_user=offset_user,
                    limit=100,
                    q=""
                )
            )
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
            continue
        except Exception as e:
            raise e

        importers = result.importers
        if not importers:
            break

        count += len(importers)
        users = {u.id: u for u in result.users}
        last = importers[-1]
        offset_date = last.date
        last_user = users.get(last.user_id)
        if last_user:
            offset_user = raw.types.InputUser(
                user_id=last_user.id,
                access_hash=last_user.access_hash
            )
        if len(importers) < 100:
            break

    return count


# ── /approve_all ──────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approve_all") & filters.private)
async def approve_all_pending(bot: Client, m: Message):
    # non-admins must pass ad verification
    if not await require_verification(bot, m):
        return

    chat_id, title, peer = await _resolve_chat(bot, m)
    if not chat_id:
        return

    msg = await m.reply_text(f"⏳ Fetching pending requests in **{title}**…")
    try:
        approved = 0

        async def progress_cb(n):
            nonlocal approved
            approved = n
            if n % 20 == 0 and n > 0:
                try:
                    await msg.edit_text(f"⏳ Approved **{n}** so far in **{title}**…")
                except Exception:
                    pass

        # Run with progress updates
        offset_date = 0
        offset_user = raw.types.InputUserEmpty()

        while True:
            try:
                result = await bot.invoke(
                    raw.functions.messages.GetChatInviteImporters(
                        peer=peer,
                        requested=True,
                        offset_date=offset_date,
                        offset_user=offset_user,
                        limit=100,
                        q=""
                    )
                )
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                continue

            importers = result.importers
            if not importers:
                break

            users = {u.id: u for u in result.users}

            for imp in importers:
                try:
                    user = users.get(imp.user_id)
                    if not user:
                        continue
                    input_user = raw.types.InputUser(
                        user_id=user.id,
                        access_hash=user.access_hash
                    )
                    await bot.invoke(
                        raw.functions.messages.HideChatJoinRequest(
                            peer=peer,
                            user_id=input_user,
                            approved=True
                        )
                    )
                    approved += 1
                    if approved % 20 == 0:
                        try:
                            await msg.edit_text(f"⏳ Approved **{approved}** so far in **{title}**…")
                        except Exception:
                            pass
                    await asyncio.sleep(0.05)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 2)
                except Exception:
                    pass

            last = importers[-1]
            offset_date = last.date
            last_user = users.get(last.user_id)
            if last_user:
                offset_user = raw.types.InputUser(
                    user_id=last_user.id,
                    access_hash=last_user.access_hash
                )
            if len(importers) < 100:
                break

        await msg.edit_text(
            f"✅ **Done!**\n\n📋 Chat: **{title}**\n👥 Approved: `{approved}` pending requests"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{e}`")


# ── /decline_all ──────────────────────────────────────────────────────────────

@Client.on_message(filters.command("decline_all") & admin_filter & filters.private)
async def decline_all_pending(bot: Client, m: Message):
    chat_id, title, peer = await _resolve_chat(bot, m)
    if not chat_id:
        return

    await m.reply_text(
        f"⚠️ Decline **ALL** pending requests in **{title}**?\nThis cannot be undone.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, decline all", callback_data=f"decline_confirm:{chat_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="decline_cancel")
        ]])
    )


# Store peer temporarily for decline confirm (in-memory)
_decline_peers: dict = {}


@Client.on_message(filters.command("decline_all") & admin_filter & filters.private)
async def _store_decline_peer(bot: Client, m: Message):
    pass  # handled above, peer cached via resolve inside callback


@Client.on_callback_query(filters.regex(r"^decline_confirm:(-?\d+)$") & admin_filter)
async def decline_confirm_cb(bot: Client, cb: CallbackQuery):
    chat_id = int(cb.data.split(":")[1])
    await cb.message.edit_text("⏳ Declining all pending requests…")
    try:
        chat = await bot.get_chat(chat_id)
        peer = await bot.resolve_peer(chat_id)

        declined = 0
        offset_date = 0
        offset_user = raw.types.InputUserEmpty()

        while True:
            try:
                result = await bot.invoke(
                    raw.functions.messages.GetChatInviteImporters(
                        peer=peer,
                        requested=True,
                        offset_date=offset_date,
                        offset_user=offset_user,
                        limit=100,
                        q=""
                    )
                )
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                continue

            importers = result.importers
            if not importers:
                break

            users = {u.id: u for u in result.users}
            for imp in importers:
                try:
                    user = users.get(imp.user_id)
                    if not user:
                        continue
                    input_user = raw.types.InputUser(user_id=user.id, access_hash=user.access_hash)
                    await bot.invoke(
                        raw.functions.messages.HideChatJoinRequest(
                            peer=peer, user_id=input_user, approved=False
                        )
                    )
                    declined += 1
                    await asyncio.sleep(0.05)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 2)
                except Exception:
                    pass

            last = importers[-1]
            offset_date = last.date
            last_user = users.get(last.user_id)
            if last_user:
                offset_user = raw.types.InputUser(user_id=last_user.id, access_hash=last_user.access_hash)
            if len(importers) < 100:
                break

        await cb.message.edit_text(
            f"🗑 **Done!**\n\n📋 Chat: **{chat.title}**\n❌ Declined: `{declined}` requests"
        )
    except Exception as e:
        await cb.message.edit_text(f"❌ Error: `{e}`")


@Client.on_callback_query(filters.regex("^decline_cancel$") & admin_filter)
async def decline_cancel_cb(bot: Client, cb: CallbackQuery):
    await cb.message.edit_text("✅ Cancelled. No requests were declined.")


# ── /pending_count ────────────────────────────────────────────────────────────

@Client.on_message(filters.command("pending_count") & admin_filter & filters.private)
async def pending_count(bot: Client, m: Message):
    chat_id, title, peer = await _resolve_chat(bot, m)
    if not chat_id:
        return
    msg = await m.reply_text("⏳ Counting pending requests…")
    try:
        count = 0
        offset_date = 0
        offset_user = raw.types.InputUserEmpty()

        while True:
            try:
                result = await bot.invoke(
                    raw.functions.messages.GetChatInviteImporters(
                        peer=peer,
                        requested=True,
                        offset_date=offset_date,
                        offset_user=offset_user,
                        limit=100,
                        q=""
                    )
                )
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                continue

            importers = result.importers
            if not importers:
                break
            count += len(importers)
            users = {u.id: u for u in result.users}
            last = importers[-1]
            offset_date = last.date
            last_user = users.get(last.user_id)
            if last_user:
                offset_user = raw.types.InputUser(user_id=last_user.id, access_hash=last_user.access_hash)
            if len(importers) < 100:
                break

        await msg.edit_text(
            f"📊 **Pending Requests**\n\n📋 Chat: **{title}**\n⏳ Pending: `{count}` requests"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{e}`")
