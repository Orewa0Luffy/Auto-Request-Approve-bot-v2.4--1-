import motor.motor_asyncio, time
from configs import rkn1


class Database:
    def __init__(self, uri, database_name):
        self._client  = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db       = self._client[database_name]
        self.col      = self.db.user
        self.chat     = self.db.chat
        self.admins   = self.db.admins
        self.buttons  = self.db.welcome_buttons
        self.welcome  = self.db.welcome_cfg
        self.settings = self.db.bot_settings    # live config (fsub, shortener…)
        self.tokens   = self.db.verify_tokens   # ad-verify tokens

    # ── users ────────────────────────────────────────────────────────────────
    def new_user(self, id): return dict(_id=int(id))

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            await self.col.insert_one(self.new_user(u.id))
            await self._send_user_log(b, u)

    async def is_user_exist(self, id):
        return bool(await self.col.find_one({'_id': int(id)}))

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    async def _send_user_log(self, b, u):
        cfg = await self.get_setting('log_channel')
        ch  = cfg or rkn1.LOG_CHANNEL
        if ch:
            try:
                await b.send_message(ch,
                    f"**New User**\nUser: {u.mention}\nID: `{u.id}`\nUsername: @{u.username}")
            except Exception: pass

    # ── chats ────────────────────────────────────────────────────────────────
    async def add_chat(self, b, m):
        if not await self.is_chat_exist(m.chat.id):
            await self.chat.insert_one(self.new_user(m.chat.id))
            await self._send_chat_log(b, m)

    async def is_chat_exist(self, id):
        return bool(await self.chat.find_one({'_id': int(id)}))

    async def total_chats_count(self):
        return await self.chat.count_documents({})

    async def get_all_chats(self):
        return self.chat.find({})

    async def delete_chat(self, chat_id):
        await self.chat.delete_many({'_id': int(chat_id)})

    async def _send_chat_log(self, b, m):
        cfg = await self.get_setting('log_channel')
        ch  = cfg or rkn1.LOG_CHANNEL
        if ch:
            try:
                await b.send_message(ch,
                    f"**New Chat**\nChat: {m.chat.title}\nID: `{m.chat.id}`\nBy: {m.from_user.mention}")
            except Exception: pass

    # ── runtime admins ────────────────────────────────────────────────────────
    async def add_admin(self, user_id: int):
        if not await self.is_admin(user_id):
            await self.admins.insert_one({'_id': user_id})

    async def remove_admin(self, user_id: int):
        await self.admins.delete_one({'_id': user_id})

    async def is_admin(self, user_id: int) -> bool:
        return bool(await self.admins.find_one({'_id': user_id}))

    async def get_all_admins(self):
        return [doc['_id'] async for doc in self.admins.find({})]

    # ── welcome buttons ───────────────────────────────────────────────────────
    async def get_welcome_buttons(self):
        doc = await self.buttons.find_one({'_id': 'cfg'})
        return doc.get('buttons', []) if doc else []

    async def set_welcome_buttons(self, btn_list: list):
        await self.buttons.update_one({'_id': 'cfg'}, {'$set': {'buttons': btn_list}}, upsert=True)

    # ── welcome media / caption ───────────────────────────────────────────────
    async def get_welcome_cfg(self):
        doc = await self.welcome.find_one({'_id': 'cfg'})
        if doc: doc.pop('_id', None)
        return doc or {}

    async def set_welcome_cfg(self, **kwargs):
        await self.welcome.update_one({'_id': 'cfg'}, {'$set': kwargs}, upsert=True)

    # ── live bot settings ─────────────────────────────────────────────────────
    # keys: force_sub, log_channel, shortener_api, shortener_site, verify_timeout
    async def get_setting(self, key: str):
        doc = await self.settings.find_one({'_id': key})
        return doc['value'] if doc else None

    async def set_setting(self, key: str, value):
        await self.settings.update_one({'_id': key}, {'$set': {'value': value}}, upsert=True)

    async def del_setting(self, key: str):
        await self.settings.delete_one({'_id': key})

    async def get_all_settings(self):
        return {doc['_id']: doc['value'] async for doc in self.settings.find({})}

    # ── ad-verify tokens ──────────────────────────────────────────────────────
    async def save_token(self, user_id: int, token: str, timeout: int):
        expires = time.time() + timeout
        await self.tokens.update_one(
            {'_id': user_id},
            {'$set': {'token': token, 'expires': expires, 'used': False}},
            upsert=True
        )

    async def get_token(self, user_id: int):
        return await self.tokens.find_one({'_id': user_id})

    async def mark_token_used(self, user_id: int):
        await self.tokens.update_one({'_id': user_id}, {'$set': {'used': True}})

    async def delete_token(self, user_id: int):
        await self.tokens.delete_one({'_id': user_id})

    async def is_verified(self, user_id: int) -> bool:
        doc = await self.tokens.find_one({'_id': user_id})
        if not doc: return False
        if doc.get('used'): return False
        if time.time() > doc.get('expires', 0): return False
        return True


rkn_botz = Database(rkn1.DB_URL, rkn1.DB_NAME)
