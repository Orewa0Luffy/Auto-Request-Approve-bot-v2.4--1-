# verify.py — ad verification gate for non-admin users
# NOTE: No /start handler here — handled entirely in start_&_cb.py to avoid conflicts

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from RknDeveloper.database import rkn_botz
from RknDeveloper.shortener import create_verify_link, handle_verify_token, is_user_verified
from configs import rkn1


async def require_verification(bot: Client, m: Message) -> bool:
    """
    Returns True  → user can proceed (admin or already verified or no shortener set).
    Returns False → sends verification prompt and blocks the command.
    """
    uid = m.from_user.id

    # Admins always bypass
    if uid in rkn1.ADMIN or await rkn_botz.is_admin(uid):
        return True

    # Already verified?
    if await is_user_verified(uid):
        return True

    # No shortener configured → allow everyone
    api = await rkn_botz.get_setting('shortener_api') or rkn1.SHORTENER_API
    if not api:
        return True

    # Generate short ad link
    short_link, token = await create_verify_link(bot.username, uid)
    timeout = await rkn_botz.get_setting('verify_timeout') or rkn1.VERIFY_TIMEOUT
    mins = int(timeout) // 60

    await m.reply_text(
        f"⚠️ **Verification Required**\n\n"
        f"To use bulk approve you must verify by watching a short ad.\n"
        f"This supports the bot ❤️\n\n"
        f"1️⃣ Tap **Verify Now**\n"
        f"2️⃣ Complete the short ad\n"
        f"3️⃣ You'll land back in the bot ✅\n"
        f"4️⃣ Run the command again\n\n"
        f"⏳ Verification valid for **{mins} minutes**.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Verify Now", url=short_link)
        ], [
            InlineKeyboardButton("✅ I've Verified", callback_data=f"chkv:{token}")
        ]])
    )
    return False


@Client.on_callback_query(filters.regex(r"^chkv:(.+)$"))
async def check_verify_cb(bot: Client, cb: CallbackQuery):
    uid   = cb.from_user.id
    token = cb.data.split(":", 1)[1]

    if await is_user_verified(uid):
        return await cb.message.edit_text(
            "✅ **You're verified!** Run your command now.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Home", callback_data="start")
            ]])
        )

    ok = await handle_verify_token(uid, token)
    if ok:
        await cb.message.edit_text(
            "✅ **Verified!** You can now use bulk approve.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Home", callback_data="start")
            ]])
        )
    else:
        await cb.answer("❌ Not verified yet. Please complete the ad first.", show_alert=True)
