# fs.py — Force subscribe check (uses live setting from DB if available)

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant


async def force_sub(bot, message, sub_id):
    if not sub_id or str(sub_id) == "0":
        return
    try:
        chat = await bot.get_chat(int(sub_id))
    except Exception:
        return  # invalid chat — skip silently

    try:
        member = await bot.get_chat_member(sub_id, message.from_user.id)
        # If banned/left/kicked still block
        from pyrogram.enums import ChatMemberStatus
        if member.status in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT):
            raise UserNotParticipant
    except UserNotParticipant:
        invite = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
        if not invite:
            try:
                invite = await bot.export_chat_invite_link(chat.id)
            except Exception:
                return

        await message.reply_text(
            f"👋 Hello {message.from_user.mention},\n\n"
            f"Please join our channel first to use this bot 😇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Join {chat.title}", url=invite)
            ]])
        )
        return True  # blocked
    except Exception:
        pass  # any other error — don't block user
