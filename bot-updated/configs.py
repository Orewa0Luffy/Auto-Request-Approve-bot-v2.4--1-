from os import getenv
import os, time

class Config:
    API_ID    = int(getenv("API_ID", "28713982"))
    API_HASH  = getenv("API_HASH", "237e15f7c006b10b4fa7c46fee7a5377")
    BOT_TOKEN = getenv("BOT_TOKEN", "7742892578:AAGByEJgHYDTK8HBzGSfp6qii-QysLQ3hoY")

    ADMIN       = list(map(int, getenv("ADMIN", "8138117720").split()))
    LOG_CHANNEL = int(getenv("LOG_CHANNEL", "-1002100963256"))
    FORCE_SUB   = int(getenv("FORCE_SUB", "0"))

    DB_URL  = getenv("DB_URL", "mongodb+srv://jepet68259_db_user:animeotaku109@cluster0.c2yjqsr.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DB_NAME = getenv("DB_NAME", "Pending_Request_Auto_Accept_Bot")

    WEBHOOK     = bool(getenv("WEBHOOK", True))
    BOT_UPTIME  = time.time()
    PORT        = getenv("PORT", "8080")

    RKN_PIC  = getenv("RKN_PIC", "https://ibb.co/tM64PbWS")
    SURPRICE = getenv("SURPRICE",
        "https://telegra.ph/file/a5a2bb456bf3eecdbbb99.mp4 "
        "https://telegra.ph/file/03c6e49bea9ce6c908b87.mp4 "
        "https://telegra.ph/file/9ebf412f09cd7d2ceaaef.mp4 "
        "https://telegra.ph/file/293cc10710e57530404f8.mp4 "
        "https://telegra.ph/file/506898de518534ff68ba0.mp4"
    ).split()

    # ── Shortener (default / fallback) ──────────────────────────────────────
    # These are the bot-owner defaults. Admins can override per-bot via DB.
    SHORTENER_API  = getenv("SHORTENER_API", "")   # e.g. shrinkme.io API key
    SHORTENER_SITE = getenv("SHORTENER_SITE", "")  # domain

    # How long (seconds) an ad-verification token stays valid
    VERIFY_TIMEOUT = int(getenv("VERIFY_TIMEOUT", "900"))  # 15 min default

    LOGO = """
╔═╗╔╦╗╔═╦╗  ╔══╗╔═╗╔╗─╔╗╔═╗╔╗─╔═╗╔═╗╔═╗╔═╗
║╬║║╔╝║║║║  ╚╗╗║║╦╝║╚╦╝║║╦╝║║─║║║║╬║║╦╝║╬║
║╗╣║╚╗║║║║  ╔╩╝║║╩╗╚╗║╔╝║╩╗║╚╗║║║║╔╝║╩╗║╗╣
╚╩╝╚╩╝╚╩═╝  ╚══╝╚═╝─╚═╝─╚═╝╚═╝╚═╝╚╝─╚═╝╚╩╝"""

rkn1 = Config()