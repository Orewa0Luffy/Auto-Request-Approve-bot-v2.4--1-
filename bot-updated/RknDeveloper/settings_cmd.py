# settings_cmd.py — Live bot config panel for super-admins
# /settings shows inline buttons; replies are caught by the text handler below.
# IMPORTANT: This handler uses group=2 (lower priority) so commands like /start
# run first and don't get swallowed here.

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from RknDeveloper.database import rkn_botz
from configs import rkn1

# in-memory state: uid → key being edited
_waiting: dict[int, str] = {}


# ══════════════════════════════════════════════════════════════
#  /settings panel
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.command("settings") & filters.user(rkn1.ADMIN) & filters.private)
async def show_settings(bot: Client, m: Message):
    txt, kb = await _build_panel()
    await m.reply_text(txt, reply_markup=kb)


@Client.on_callback_query(filters.regex("^settings_home$") & filters.user(rkn1.ADMIN))
async def settings_home_cb(bot: Client, cb: CallbackQuery):
    txt, kb = await _build_panel()
    await cb.message.edit_text(txt, reply_markup=kb)


async def _build_panel():
    s = await rkn_botz.get_all_settings()

    fsub    = s.get('force_sub')     or rkn1.FORCE_SUB    or "❌ Off"
    logch   = s.get('log_channel')   or rkn1.LOG_CHANNEL  or "❌ Off"
    sh_api  = s.get('shortener_api') or rkn1.SHORTENER_API
    sh_site = s.get('shortener_site')or rkn1.SHORTENER_SITE or "❌ Not set"
    timeout = s.get('verify_timeout')or rkn1.VERIFY_TIMEOUT or 900

    api_disp = f"✅ `{str(sh_api)[:6]}…`" if sh_api else "❌ Not set"

    txt = (
        "⚙️ **Live Bot Settings**\n\n"
        f"📢 **Force Sub:**      `{fsub}`\n"
        f"📋 **Log Channel:**   `{logch}`\n"
        f"🔗 **Shortener Site:** `{sh_site}`\n"
        f"🔑 **Shortener API:**  {api_disp}\n"
        f"⏳ **Verify Timeout:** `{timeout}s` ({int(timeout)//60} min)\n\n"
        "_Tap a button to change any value._"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Force Sub",       callback_data="cfg:force_sub"),
         InlineKeyboardButton("📋 Log Channel",     callback_data="cfg:log_channel")],
        [InlineKeyboardButton("🔗 Shortener Site",  callback_data="cfg:shortener_site"),
         InlineKeyboardButton("🔑 Shortener API",   callback_data="cfg:shortener_api")],
        [InlineKeyboardButton("⏳ Verify Timeout",  callback_data="cfg:verify_timeout")],
        [InlineKeyboardButton("🗑 Reset All to ENV", callback_data="cfg:reset")],
    ])
    return txt, kb


# ══════════════════════════════════════════════════════════════
#  Tap a setting button → show prompt
# ══════════════════════════════════════════════════════════════

_prompts = {
    'force_sub': (
        "📢 **Set Force Subscribe**\n\n"
        "Send the channel/group **ID** (e.g. `-1001234567890`) or **@username**.\n"
        "Send `0` to disable."
    ),
    'log_channel': (
        "📋 **Set Log Channel**\n\n"
        "Send the channel **ID**. Bot must be admin there.\n"
        "Send `0` to disable."
    ),
    'shortener_site': (
        "🔗 **Set Shortener Domain**\n\n"
        "Send domain without https://\n\n"
        "Examples:\n"
        "• `shrinkme.io`\n• `earnpay.net`\n• `gplinks.in`\n• `adfoc.us`"
    ),
    'shortener_api': (
        "🔑 **Set Shortener API Key**\n\n"
        "Send your API key from the shortener dashboard.\n"
        "Send `remove` to disable ad verification."
    ),
    'verify_timeout': (
        "⏳ **Set Verify Timeout (seconds)**\n\n"
        "How long a verification stays valid:\n"
        "• `900` = 15 min\n• `3600` = 1 hour\n• `86400` = 24 hours"
    ),
}


@Client.on_callback_query(filters.regex(r"^cfg:(.+)$") & filters.user(rkn1.ADMIN))
async def cfg_button_cb(bot: Client, cb: CallbackQuery):
    key = cb.data.split(":", 1)[1]

    if key == "reset":
        for k in ['force_sub', 'log_channel', 'shortener_api', 'shortener_site', 'verify_timeout']:
            await rkn_botz.del_setting(k)
        await cb.answer("✅ All settings reset to ENV defaults.", show_alert=True)
        txt, kb = await _build_panel()
        return await cb.message.edit_text(txt, reply_markup=kb)

    prompt = _prompts.get(key, f"Send new value for `{key}`:")
    _waiting[cb.from_user.id] = key
    await cb.message.edit_text(
        prompt,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="settings_home")
        ]])
    )


# ══════════════════════════════════════════════════════════════
#  Catch the reply value — group=1 so it runs BEFORE default
#  text handlers, but only when _waiting state is set
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.private & filters.text & filters.user(rkn1.ADMIN), group=1)
async def catch_setting_reply(bot: Client, m: Message):
    uid = m.from_user.id
    if uid not in _waiting:
        return  # no state — pass through to other handlers

    # Don't intercept bot commands
    if m.text and m.text.startswith("/"):
        return

    key = _waiting.pop(uid)
    val = m.text.strip()

    # remove / disable
    if val.lower() in ("remove", "disable", "off", "none") and key not in ("force_sub", "log_channel", "verify_timeout"):
        await rkn_botz.del_setting(key)
        return await m.reply_text(
            f"✅ **{_label(key)}** disabled.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to Settings", callback_data="settings_home")
            ]])
        )

    # zero = disable for numeric channel/chat fields
    if val == "0" and key in ("force_sub", "log_channel"):
        await rkn_botz.del_setting(key)
        return await m.reply_text(
            f"✅ **{_label(key)}** disabled.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to Settings", callback_data="settings_home")
            ]])
        )

    # Validate & coerce
    if key in ("force_sub", "log_channel"):
        if val.lstrip("-").isdigit():
            val = int(val)
        else:
            try:
                chat = await bot.get_chat(val)
                val  = chat.id
            except Exception:
                return await m.reply_text("❌ Invalid chat ID or username. Try again.")

    elif key == "verify_timeout":
        if not val.isdigit():
            return await m.reply_text("❌ Send a number (seconds). E.g. `900`")
        val = int(val)
        if val < 60:
            return await m.reply_text("❌ Minimum is 60 seconds.")

    elif key == "shortener_site":
        val = val.lstrip("https://").lstrip("http://").rstrip("/")

    await rkn_botz.set_setting(key, val)

    display = str(val)
    if key == "shortener_api" and len(display) > 8:
        display = display[:6] + "…" + display[-4:]

    await m.reply_text(
        f"✅ **{_label(key)}** set to `{display}`",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⚙️ Back to Settings", callback_data="settings_home")
        ]])
    )


def _label(key):
    return {
        'force_sub':      'Force Subscribe',
        'log_channel':    'Log Channel',
        'shortener_api':  'Shortener API Key',
        'shortener_site': 'Shortener Domain',
        'verify_timeout': 'Verify Timeout',
    }.get(key, key)
