# admin.py  –  Admin management + broadcast + stats + restart + welcome setup

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

import os, sys, time, asyncio, datetime, logging
from RknDeveloper.database import rkn_botz
from configs import rkn1

logger = logging.getLogger(__name__)


# ── Combined admin filter (ENV list + DB runtime admins) ─────────────────────

def is_admin_filter():
    async def func(_, __, m):
        uid = m.from_user.id if m.from_user else None
        if uid is None: return False
        return uid in rkn1.ADMIN or await rkn_botz.is_admin(uid)
    return filters.create(func)

admin_filter = is_admin_filter()


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN MANAGEMENT  (super-admins only)
# ════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("addadmin") & filters.user(rkn1.ADMIN) & filters.private)
async def add_admin_cmd(bot: Client, m: Message):
    target_id = await _parse_user_id(m)
    if target_id is None:
        return await m.reply_text("❌ Usage: `/addadmin <user_id>`")
    if target_id in rkn1.ADMIN:
        return await m.reply_text("⚠️ Already a super-admin (ENV).")
    if await rkn_botz.is_admin(target_id):
        return await m.reply_text("⚠️ Already an admin.")
    await rkn_botz.add_admin(target_id)
    name = await _get_name(bot, target_id)
    await m.reply_text(f"✅ **{name}** (`{target_id}`) added as admin.")
    await _log(bot, f"👤 **Admin Added**\nBy: {m.from_user.mention}\nNew: {name} (`{target_id}`)")


@Client.on_message(filters.command("deladmin") & filters.user(rkn1.ADMIN) & filters.private)
async def del_admin_cmd(bot: Client, m: Message):
    target_id = await _parse_user_id(m)
    if target_id is None:
        return await m.reply_text("❌ Usage: `/deladmin <user_id>`")
    if target_id in rkn1.ADMIN:
        return await m.reply_text("❌ Cannot remove a super-admin set in ENV.")
    if not await rkn_botz.is_admin(target_id):
        return await m.reply_text("⚠️ This user is not an admin.")
    await rkn_botz.remove_admin(target_id)
    name = await _get_name(bot, target_id)
    await m.reply_text(f"🗑 **{name}** (`{target_id}`) removed from admins.")
    await _log(bot, f"🗑 **Admin Removed**\nBy: {m.from_user.mention}\nRemoved: {name} (`{target_id}`)")


@Client.on_message(filters.command("admins") & filters.user(rkn1.ADMIN) & filters.private)
async def list_admins_cmd(bot: Client, m: Message):
    lines = ["**👑 Super Admins (ENV):**"]
    for uid in rkn1.ADMIN:
        lines.append(f"  • {await _get_name(bot, uid)} — `{uid}`")
    db_admins = await rkn_botz.get_all_admins()
    lines.append("\n**🛡 Runtime Admins (DB):**")
    if db_admins:
        for uid in db_admins:
            lines.append(f"  • {await _get_name(bot, uid)} — `{uid}`")
    else:
        lines.append("  _None added yet._")
    await m.reply_text("\n".join(lines))


# ════════════════════════════════════════════════════════════════════════════
#  STATS & RESTART
# ════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command(["stats", "status"]) & admin_filter)
async def get_stats(bot: Client, m: Message):
    total_users = await rkn_botz.total_users_count()
    total_chats = await rkn_botz.total_chats_count()
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - bot.uptime))
    t0  = time.time()
    msg = await m.reply_text("⏳ Processing…")
    ping = (time.time() - t0) * 1000
    await msg.edit_text(
        f"**📊 Bot Status**\n\n"
        f"⌚️ Uptime: `{uptime}`\n"
        f"🏓 Ping: `{ping:.2f} ms`\n"
        f"👥 Total Users: `{total_users}`\n"
        f"💬 Total Chats: `{total_chats}`"
    )


@Client.on_message(filters.private & filters.command("restart") & filters.user(rkn1.ADMIN))
async def restart_bot(bot: Client, m: Message):
    await m.reply_text("🔄 Restarting…")
    os.execl(sys.executable, sys.executable, *sys.argv)


# ════════════════════════════════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("broadcast") & admin_filter & filters.reply & filters.private)
async def broadcast_handler(bot: Client, m: Message):
    broadcast_msg = m.reply_to_message
    sts   = await m.reply_text("📢 Broadcast started…")
    await _log(bot, f"📢 **Broadcast started** by {m.from_user.mention}")

    all_users = await rkn_botz.get_all_users()
    total     = await rkn_botz.total_users_count()
    done = success = failed = 0
    start = time.time()

    async for user in all_users:
        code = await _send_msg(user['_id'], broadcast_msg)
        if code == 200: success += 1
        else:           failed  += 1
        if code == 400: await rkn_botz.delete_user(user['_id'])
        done += 1
        if done % 25 == 0:
            try:
                await sts.edit_text(
                    f"📢 **Broadcasting…**\n\n"
                    f"Total: {total} | Done: {done}\n"
                    f"✅ {success} | ❌ {failed}"
                )
            except Exception: pass

    elapsed = datetime.timedelta(seconds=int(time.time() - start))
    await sts.edit_text(
        f"✅ **Broadcast Done**\n\n"
        f"⏱ Time: `{elapsed}`\nTotal: `{total}`\n"
        f"✅ Success: `{success}` | ❌ Failed: `{failed}`"
    )


# ════════════════════════════════════════════════════════════════════════════
#  WELCOME MESSAGE SETUP
# ════════════════════════════════════════════════════════════════════════════

SETBTN_HELP = (
    "**Button Format (one button per line):**\n"
    "```\nButton Label - https://t.me/channel```\n\n"
    "Side-by-side (use `|`):\n"
    "```\nBtn1 - https://url1 | Btn2 - https://url2```\n\n"
    "Variables in caption: `{name}` `{chat}`"
)


@Client.on_message(filters.command("setbuttons") & admin_filter & filters.private)
async def set_buttons_cmd(bot: Client, m: Message):
    lines = m.text.split("\n")[1:]
    if not lines or all(l.strip() == "" for l in lines):
        return await m.reply_text(SETBTN_HELP)

    btn_rows, errors = [], []
    for i, line in enumerate(lines, 1):
        row = []
        for part in line.split("|"):
            part = part.strip()
            if not part: continue
            if " - " not in part:
                errors.append(f"Row {i}: missing ` - ` in `{part}`")
                continue
            label, url = part.split(" - ", 1)
            if not url.strip().startswith("http"):
                errors.append(f"Row {i}: URL must start with http")
                continue
            row.append({"label": label.strip(), "url": url.strip()})
        if row: btn_rows.append(row)

    if errors:
        return await m.reply_text("❌ Errors:\n" + "\n".join(errors) + "\n\n" + SETBTN_HELP)

    await rkn_botz.set_welcome_buttons(btn_rows)
    total = sum(len(r) for r in btn_rows)
    await m.reply_text(f"✅ Saved **{total}** button(s) in **{len(btn_rows)}** row(s).")


@Client.on_message(filters.command("buttons") & admin_filter & filters.private)
async def view_buttons_cmd(bot: Client, m: Message):
    rows = await rkn_botz.get_welcome_buttons()
    if not rows:
        return await m.reply_text("No buttons set yet.\n\n" + SETBTN_HELP)
    lines = ["**Current Welcome Buttons:**\n"]
    for r_i, row in enumerate(rows, 1):
        for c_i, btn in enumerate(row, 1):
            lines.append(f"  Row {r_i}, Col {c_i}: **{btn['label']}** → `{btn['url']}`")
    lines.append("\nUse `/delbutton <row> <col>` to remove one.")
    await m.reply_text("\n".join(lines))


@Client.on_message(filters.command("delbutton") & admin_filter & filters.private)
async def del_button_cmd(bot: Client, m: Message):
    parts = m.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await m.reply_text("Usage: `/delbutton <row> <col>`  (1-indexed)")
    row_i, col_i = int(parts[1]) - 1, int(parts[2]) - 1
    rows = await rkn_botz.get_welcome_buttons()
    if row_i >= len(rows): return await m.reply_text(f"❌ Row {row_i+1} doesn't exist.")
    if col_i >= len(rows[row_i]): return await m.reply_text(f"❌ Col {col_i+1} doesn't exist.")
    removed = rows[row_i].pop(col_i)
    if not rows[row_i]: rows.pop(row_i)
    await rkn_botz.set_welcome_buttons(rows)
    await m.reply_text(f"🗑 Removed **{removed['label']}**.")


@Client.on_message(filters.command("clearbuttons") & admin_filter & filters.private)
async def clear_buttons_cmd(bot: Client, m: Message):
    await rkn_botz.set_welcome_buttons([])
    await m.reply_text("🗑 All welcome buttons cleared.")


@Client.on_message(filters.command("setwelcome") & admin_filter & filters.private)
async def set_welcome_cmd(bot: Client, m: Message):
    if m.reply_to_message:
        reply = m.reply_to_message
        caption = m.text.split(None, 1)[1] if len(m.text.split(None, 1)) > 1 else ""
        if reply.photo:
            await rkn_botz.set_welcome_cfg(media_type="photo", file_id=reply.photo.file_id, caption=caption)
            return await m.reply_text("✅ Welcome **photo** saved!")
        elif reply.animation:
            await rkn_botz.set_welcome_cfg(media_type="gif", file_id=reply.animation.file_id, caption=caption)
            return await m.reply_text("✅ Welcome **GIF** saved!")
        elif reply.video:
            await rkn_botz.set_welcome_cfg(media_type="video", file_id=reply.video.file_id, caption=caption)
            return await m.reply_text("✅ Welcome **video** saved!")

    caption = m.text.split(None, 1)[1] if len(m.text.split(None, 1)) > 1 else ""
    if not caption:
        return await m.reply_text(
            "**Usage:**\n"
            "• Reply to a photo/GIF/video with `/setwelcome [caption]`\n"
            "• Or `/setwelcome <text>` for caption only\n\n"
            "**Variables:** `{name}` `{chat}`"
        )
    await rkn_botz.set_welcome_cfg(caption=caption)
    await m.reply_text("✅ Welcome caption updated!")


@Client.on_message(filters.command("welcomeinfo") & admin_filter & filters.private)
async def welcome_info_cmd(bot: Client, m: Message):
    cfg  = await rkn_botz.get_welcome_cfg()
    rows = await rkn_botz.get_welcome_buttons()
    if not cfg and not rows:
        return await m.reply_text("No custom welcome set. Bot uses default.")
    text  = "**Current Welcome Config:**\n\n"
    text += f"Media: `{cfg.get('media_type', 'none')}`\n"
    text += f"Caption: `{cfg.get('caption', '(default)')[:80]}`\n"
    text += f"Buttons: `{sum(len(r) for r in rows)}` button(s)\n"
    await m.reply_text(text)


@Client.on_message(filters.command("resetwelcome") & filters.user(rkn1.ADMIN) & filters.private)
async def reset_welcome_cmd(bot: Client, m: Message):
    await rkn_botz.set_welcome_cfg(media_type=None, file_id=None, caption=None)
    await rkn_botz.set_welcome_buttons([])
    await m.reply_text("✅ Welcome reset to default.")


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

async def _parse_user_id(m: Message):
    parts = m.text.split()
    if len(parts) > 1:
        try: return int(parts[1])
        except ValueError: pass
    if m.reply_to_message and m.reply_to_message.forward_from:
        return m.reply_to_message.forward_from.id
    return None


async def _get_name(bot: Client, uid: int) -> str:
    try:
        u = await bot.get_users(uid)
        return u.mention
    except Exception:
        return f"`{uid}`"


async def _log(bot: Client, text: str):
    ch = await rkn_botz.get_setting('log_channel') or rkn1.LOG_CHANNEL
    if ch:
        try: await bot.send_message(ch, text)
        except Exception: pass


async def _send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await _send_msg(user_id, message)
    except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
        return 400
    except Exception as e:
        logger.error(f"broadcast {user_id}: {e}")
        return 500
