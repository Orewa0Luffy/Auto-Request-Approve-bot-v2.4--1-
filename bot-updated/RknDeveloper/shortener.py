# shortener.py  –  Ad-verification via link shortener
# Supports: ShrinkMe, EarnPay, AdFly, GPLinks, and any shrinkme-compatible API

import aiohttp, hashlib, time, secrets
from RknDeveloper.database import rkn_botz
from configs import rkn1


# ── Get active shortener config (DB overrides ENV) ────────────────────────────

async def get_shortener_cfg():
    api  = await rkn_botz.get_setting('shortener_api')  or rkn1.SHORTENER_API
    site = await rkn_botz.get_setting('shortener_site') or rkn1.SHORTENER_SITE
    timeout = await rkn_botz.get_setting('verify_timeout') or rkn1.VERIFY_TIMEOUT
    return api, site, int(timeout)


# ── Shorten a URL via the configured API ──────────────────────────────────────

async def shorten_url(long_url: str) -> str | None:
    api, site, _ = await get_shortener_cfg()
    if not api:
        return None

    site = site.strip().rstrip('/')

    # ShrinkMe / EarnPay / most compatible APIs
    api_url = f"https://{site}/api?api={api}&url={long_url}&format=text"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    short = (await r.text()).strip()
                    if short.startswith("http"):
                        return short
    except Exception as e:
        print(f"[shortener] error: {e}")
    return None


# ── Generate a verify token and a short link ──────────────────────────────────

async def create_verify_link(bot_username: str, user_id: int) -> tuple[str, str]:
    """
    Returns (short_link, raw_token).
    The raw_token is stored in DB; user must open the short link (which
    redirects to t.me/bot?start=verify_<token>) to prove they watched the ad.
    """
    _, _, timeout = await get_shortener_cfg()
    token = secrets.token_urlsafe(16)
    await rkn_botz.save_token(user_id, token, timeout)

    deep_link = f"https://t.me/{bot_username}?start=verify_{token}"
    short = await shorten_url(deep_link)
    return short or deep_link, token


# ── Check if user is verified ─────────────────────────────────────────────────

async def is_user_verified(user_id: int) -> bool:
    return await rkn_botz.is_verified(user_id)


# ── Called when user lands on ?start=verify_<token> ──────────────────────────

async def handle_verify_token(user_id: int, token: str) -> bool:
    doc = await rkn_botz.get_token(user_id)
    if not doc:
        return False
    if doc.get('used'):
        return False
    if time.time() > doc.get('expires', 0):
        await rkn_botz.delete_token(user_id)
        return False
    if doc.get('token') != token:
        return False
    # Mark as verified (don't mark used yet — stays valid until timeout)
    return True
