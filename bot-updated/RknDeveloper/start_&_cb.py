# start_&_cb.py — /start, /help, auto-approve join requests, verify deep link

from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram import filters, Client, enums, raw
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, FloodWait

from RknDeveloper.database import rkn_botz
from RknDeveloper.fs import force_sub
from configs import rkn1
import asyncio, random


# ══════════════════════════════════════════════════════════════
#  AUTO-APPROVE JOIN REQUESTS  (raw MTProto — works on pyrofork 2.3.69)
# ══════════════════════════════════════════════════════════════

@Client.on_chat_join_request()
async def approve_request(bot, m):
    try:
        await rkn_botz.add_chat(bot, m)

        # ── Approve via raw API (fixes BOT_METHOD_INVALID) ──────────────
        try:
            peer       = await bot.resolve_peer(m.chat.id)
            input_user = await bot.resolve_peer(m.from_user.id)
            await bot.invoke(
                raw.functions.messages.HideChatJoinRequest(
                    peer=peer,
                    user_id=input_user,
                    approved=True
                )
            )
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            peer       = await bot.resolve_peer(m.chat.id)
            input_user = await bot.resolve_peer(m.from_user.id)
            await bot.invoke(
                raw.functions.messages.HideChatJoinRequest(
                    peer=peer,
                    user_id=input_user,
                    approved=True
                )
            )

        await rkn_botz.add_user(bot, m)

        # ── Build welcome keyboard ───────────────────────────────────────
        rows = await rkn_botz.get_welcome_buttons()
        keyboard = [[InlineKeyboardButton(b['label'], url=b['url']) for b in row] for row in rows]
        if not keyboard:
            keyboard = [[
                InlineKeyboardButton("➕ Add Me To Channel",
                    url=f"https://t.me/{bot.username}?startchannel=true&admin=invite_users+manage_chat")
            ], [
                InlineKeyboardButton("➕ Add Me To Group",
                    url=f"https://t.me/{bot.username}?startgroup=true&admin=invite_users+manage_chat")
            ]]
        markup = InlineKeyboardMarkup(keyboard)

        # ── Build caption ────────────────────────────────────────────────
        cfg     = await rkn_botz.get_welcome_cfg()
        raw_cap = cfg.get('caption') if cfg else None
        if raw_cap:
            caption = raw_cap.replace("{name}", m.from_user.mention).replace("{chat}", m.chat.title)
        else:
            caption = (
                f"**Hey, {m.from_user.mention}! 🎉**\n\n"
                f"✅ Your join request for **{m.chat.title}** has been **accepted**!\n\n"
                f"Welcome to the community 🥳\n\n"
                f"__Powered By : @RknDeveloper__"
            )

        # ── Send welcome DM ──────────────────────────────────────────────
        media_type = cfg.get('media_type') if cfg else None
        file_id    = cfg.get('file_id')    if cfg else None
        try:
            if media_type == "photo" and file_id:
                await bot.send_photo(m.from_user.id, file_id, caption=caption, reply_markup=markup)
            elif media_type in ("gif", "video") and file_id:
                await bot.send_animation(m.from_user.id, file_id, caption=caption, reply_markup=markup)
            else:
                gif = random.choice(rkn1.SURPRICE)
                await bot.send_animation(m.from_user.id, gif, caption=caption, reply_markup=markup)
        except (UserIsBlocked, PeerIdInvalid):
            pass  # user hasn't started bot or blocked it — skip DM silently

        # ── Log to channel ───────────────────────────────────────────────
        log_ch = await rkn_botz.get_setting('log_channel') or rkn1.LOG_CHANNEL
        if log_ch:
            try:
                await bot.send_message(log_ch,
                    f"✅ **Request Approved**\n\n"
                    f"👤 {m.from_user.mention}\n"
                    f"🆔 `{m.from_user.id}`\n"
                    f"📢 **{m.chat.title}** (`{m.chat.id}`)")
            except Exception:
                pass

    except Exception as err:
        print(f"[approve_request] {err}")


# ══════════════════════════════════════════════════════════════
#  /start  — normal start + verify_TOKEN deep link
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.command("start") & filters.private)
async def start_command(bot, m: Message):
    await rkn_botz.add_user(bot, m)
    parts = (m.text or "").split()

    # ── verify deep link ─────────────────────────────────────
    if len(parts) > 1 and parts[1].startswith("verify_"):
        from RknDeveloper.shortener import create_verify_link, handle_verify_token
        token = parts[1][len("verify_"):]
        ok    = await handle_verify_token(m.from_user.id, token)
        if ok:
            timeout = await rkn_botz.get_setting('verify_timeout') or rkn1.VERIFY_TIMEOUT
            mins = int(timeout) // 60
            return await m.reply_text(
                f"✅ **Verification Successful!**\n\n"
                f"You are verified for **{mins} minutes**.\n"
                f"Go back and run `/approve_all` again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Home", callback_data="start")
                ]])
            )
        else:
            short_link, _ = await create_verify_link(bot.username, m.from_user.id)
            return await m.reply_text(
                "❌ **Verification failed** — token expired or invalid.\n\nTry again:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Verify Again", url=short_link)
                ]])
            )

    # ── force subscribe check ─────────────────────────────────
    fsub = await rkn_botz.get_setting('force_sub') or rkn1.FORCE_SUB
    if fsub and str(fsub) != "0":
        blocked = await force_sub(bot, m, fsub)
        if blocked:
            return

    # ── normal start message ──────────────────────────────────
    await m.reply_photo(
        photo=rkn1.RKN_PIC,
        caption=(
            f"**Hey, {m.from_user.mention}! 👋**\n\n"
            "I'm an **Auto Approve** bot for Telegram join requests.\n"
            "Add me to your channel or group, promote me as admin "
            "with **Add Members** permission — I'll instantly approve every request!\n\n"
            "__Powered By : @RknDeveloper__"
        ),
        reply_markup=_main_kb(bot.username)
    )


@Client.on_message(filters.command("start") & ~filters.private)
async def start_group(bot, m: Message):
    await rkn_botz.add_chat(bot, m)
    await m.reply_text(
        f"**Hello {m.from_user.first_name}! Write me in private.**",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Open Private", url=f"https://t.me/{bot.username}?start=hi")
        ]])
    )


# ══════════════════════════════════════════════════════════════
#  CALLBACK QUERIES
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex("^start$"))
async def start_cb(bot, cb: CallbackQuery):
    await cb.message.edit_text(
        f"**Hey, {cb.from_user.mention}! 👋**\n\n"
        "I'm an **Auto Approve** bot for Telegram join requests.\n"
        "Add me to your channel/group as admin with **Add Members** permission.\n\n"
        "__Powered By : @RknDeveloper__",
        reply_markup=_main_kb(bot.username),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^about$"))
async def about_cb(bot, cb: CallbackQuery):
    await cb.message.edit_text(
        "<b>ℹ️ About This Bot\n\n"
        "Name: Auto Join Request Approver\n"
        "Developer: <a href='https://t.me/RknDeveloperr'>RknDeveloper</a>\n"
        "Library: Pyrogram / Pyrofork\n"
        "Language: Python 3\n"
        "Database: MongoDB\n"
        "Version: v2.4.0</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📂 Source Code",
                url="https://github.com/RknDeveloper/Rkn_Auto-Request-Approve-bot")
        ], [
            InlineKeyboardButton("← Back", callback_data="start")
        ]])
    )


# ══════════════════════════════════════════════════════════════
#  /help
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.command("help"))
async def help_cmd(bot, m: Message):
    uid    = m.from_user.id
    is_su  = uid in rkn1.ADMIN
    is_adm = is_su or await rkn_botz.is_admin(uid)

    text = (
        "**📖 Bot Commands**\n\n"
        "/start — Start the bot\n"
        "/help — Show this message\n"
    )
    if is_adm:
        text += (
            "\n**📊 Stats & Broadcast:**\n"
            "/stats — Bot statistics\n"
            "/broadcast — Broadcast to all users _(reply to a msg)_\n"
            "\n**🎨 Welcome Message:**\n"
            "/setwelcome — Set welcome photo/GIF/caption\n"
            "/setbuttons — Set inline buttons\n"
            "/buttons — View current buttons\n"
            "/delbutton `<row> <col>` — Delete a button\n"
            "/clearbuttons — Remove all buttons\n"
            "/welcomeinfo — View welcome config\n"
            "/resetwelcome — Reset to default\n"
            "\n**⏳ Pending Requests:**\n"
            "/approve_all `<chat_id>` — Approve all pending\n"
            "/decline_all `<chat_id>` — Decline all pending\n"
            "/pending_count `<chat_id>` — Count pending\n"
        )
    if is_su:
        text += (
            "\n**👑 Super Admin:**\n"
            "/settings — View & change live bot config\n"
            "/addadmin `<id>` — Add runtime admin\n"
            "/deladmin `<id>` — Remove runtime admin\n"
            "/admins — List all admins\n"
            "/restart — Restart the bot\n"
        )
    await m.reply_text(text)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _main_kb(username):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("ℹ️ About", callback_data="about")
    ], [
        InlineKeyboardButton("📣 Updates", url="https://t.me/RknDeveloper"),
        InlineKeyboardButton("💬 Support", url="https://t.me/RknBots_Support")
    ], [
        InlineKeyboardButton("➕ Add to Channel",
            url=f"https://t.me/{username}?startchannel=true&admin=invite_users+manage_chat")
    ], [
        InlineKeyboardButton("➕ Add to Group",
            url=f"https://t.me/{username}?startgroup=true&admin=invite_users+manage_chat")
    ]])
