import os
import asyncio
import logging
import aiohttp
import glob
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest, EditPhotoRequest, InviteToChannelRequest
from telethon.tl.functions.messages import EditChatAboutRequest
from telethon.tl.types import ChatAdminRights, InputChatUploadedPhoto, InputPeerChannel
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime
from pyrogram import Client as PyroClient
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

# ══════════════════════════════════════════
os.makedirs("logs", exist_ok=True)
os.makedirs("sessions", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("logs/bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
API_ID, API_HASH, PHONE, CODE_DIGITS, PASSWORD, BOT_TOKEN_USER = range(6)
CODE_LENGTH = 5
user_data_store = {}
pyro_client = None
pytgcalls = None
music_players = {}


def get_player(chat_id):
    if chat_id not in music_players:
        music_players[chat_id] = {"queue": [], "current": None, "loop": False}
    return music_players[chat_id]


def is_valid_api_id(v): return v.isdigit()
def is_valid_api_hash(v): return len(v) == 32 and v.isalnum()


# ══════════════════════════════════════════
# يوتيوب — بدون Google API، بـ yt-dlp بس
# ══════════════════════════════════════════
async def search_and_download(query: str, chat_id: int) -> tuple:
    """بحث وتحميل في خطوة واحدة بـ yt-dlp"""
    is_url = "youtube.com" in query or "youtu.be" in query
    output_path = f"downloads/{chat_id}_%(id)s.%(ext)s"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch" if not is_url else None,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }

    loop = asyncio.get_event_loop()

    def _run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query if is_url else f"ytsearch:{query}", download=True)
            if "entries" in info:
                info = info["entries"][0]
            vid_id = info.get("id", "unknown")
            title = info.get("title", "غير معروف")
            duration_sec = info.get("duration", 0)
            m, s = divmod(int(duration_sec), 60)
            duration = f"{m}:{s:02d}"
            files = glob.glob(f"downloads/{chat_id}_{vid_id}*")
            if not files:
                raise FileNotFoundError("مش لاقي الملف")
            return files[0], title, duration

    return await loop.run_in_executor(None, _run)


def cleanup_downloads(chat_id: int):
    for f in glob.glob(f"downloads/{chat_id}_*"):
        try:
            os.remove(f)
        except Exception:
            pass


# ══════════════════════════════════════════
# إعداد PyTgCalls
# ══════════════════════════════════════════
async def setup_pytgcalls(phone, api_id, api_hash):
    global pyro_client, pytgcalls
    pyro_client = PyroClient(f"sessions/pyro_{phone}", api_id=api_id, api_hash=api_hash)
    pytgcalls = PyTgCalls(pyro_client)

    @pytgcalls.on_stream_end()
    async def on_end(client, update):
        cid = update.chat_id
        player = get_player(cid)

        if player["loop"] and player["current"]:
            try:
                await pytgcalls.change_stream(cid, MediaStream(player["current"]["file"]))
            except Exception as e:
                logger.error(f"loop error: {e}")
            return

        if player["queue"]:
            player["queue"].pop(0)

        if player["queue"]:
            nxt = player["queue"][0]
            player["current"] = nxt
            try:
                await pytgcalls.change_stream(cid, MediaStream(nxt["file"]))
                tg = user_data_store.get("client")
                if tg:
                    await tg.send_message(cid, f"🎵 التالية:\n🎧 {nxt['title']}\n⏱ {nxt['duration']}")
            except Exception as e:
                logger.error(f"auto-play error: {e}")
        else:
            player["current"] = None
            try:
                await pytgcalls.leave_group_call(cid)
                cleanup_downloads(cid)
            except Exception:
                pass

    await pyro_client.start()
    await pytgcalls.start()
    logger.info("✅ PyTgCalls ready")


# ══════════════════════════════════════════
# معالجات بوت الإعداد
# ══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store.clear()
    user_data_store["main_bot_chat_id"] = update.message.chat_id
    await update.message.reply_text(
        "🎵 أهلاً بك في تيلثون تـلـاشـاني!\n\n"
        "ابدأ بإدخال API_ID من my.telegram.org:"
    )
    return API_ID


async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not is_valid_api_id(v):
        await update.message.reply_text("⚠️ API_ID لازم يكون أرقام بس!")
        return API_ID
    user_data_store["api_id"] = int(v)
    await update.message.reply_text("🔑 ادخل API_HASH:")
    return API_HASH


async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not is_valid_api_hash(v):
        await update.message.reply_text("⚠️ API_HASH لازم يكون 32 حرف!")
        return API_HASH
    user_data_store["api_hash"] = v
    await update.message.reply_text("📱 ادخل رقم الهاتف (مثال: 201012345678):")
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_data_store["phone"] = phone
    client = TelegramClient(f"sessions/{phone}", user_data_store["api_id"], user_data_store["api_hash"])
    await client.connect()
    user_data_store["client"] = client
    user_data_store["code_digits"] = []

    if await client.is_user_authorized():
        await update.message.reply_text("✅ مسجّل دخول! جاري الإعداد...")
        await setup_pytgcalls(phone, user_data_store["api_id"], user_data_store["api_hash"])
        await update.message.reply_text("🤖 ادخل توكن البوت من @BotFather:")
        return BOT_TOKEN_USER

    try:
        await client.send_code_request(phone)
        await update.message.reply_text(f"📩 تم إرسال الكود!\nادخل الأرقام واحد واحد ({CODE_LENGTH} أرقام)\nالرقم الأول:")
        return CODE_DIGITS
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        return ConversationHandler.END


async def get_code_digits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    digit = update.message.text.strip()
    if not digit.isdigit() or len(digit) != 1:
        await update.message.reply_text("⚠️ ادخل رقم واحد بس!")
        return CODE_DIGITS

    user_data_store["code_digits"].append(digit)
    collected = len(user_data_store["code_digits"])

    if collected < CODE_LENGTH:
        await update.message.reply_text(f"الرقم {collected + 1}/{CODE_LENGTH}:")
        return CODE_DIGITS

    code = "".join(user_data_store["code_digits"])
    client = user_data_store["client"]
    phone = user_data_store["phone"]
    try:
        await client.sign_in(phone=phone, code=code)
        await update.message.reply_text("✅ تم تسجيل الدخول!")
        await setup_pytgcalls(phone, user_data_store["api_id"], user_data_store["api_hash"])
        await update.message.reply_text("🤖 ادخل توكن البوت من @BotFather:")
        return BOT_TOKEN_USER
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 ادخل كلمة السر:")
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")
        return ConversationHandler.END


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = user_data_store["client"]
    phone = user_data_store["phone"]
    try:
        await client.sign_in(password=update.message.text.strip())
        await update.message.reply_text("✅ تم تسجيل الدخول!")
        await setup_pytgcalls(phone, user_data_store["api_id"], user_data_store["api_hash"])
        await update.message.reply_text("🤖 ادخل توكن البوت من @BotFather:")
        return BOT_TOKEN_USER
    except Exception as e:
        await update.message.reply_text(f"❌ كلمة السر غلط: {e}")
        return PASSWORD


async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    user_data_store["bot_token"] = token
    try:
        b = Bot(token=token)
        await b.get_me()
    except Exception as e:
        await update.message.reply_text(f"❌ التوكن غلط: {e}")
        return BOT_TOKEN_USER

    try:
        client = user_data_store["client"]
        await update.message.reply_text("⚙️ جاري إنشاء المجموعة...")
        target_chat = await create_and_setup_group(client, token)
        user_data_store["target_chat"] = target_chat
        asyncio.create_task(start_userbot(client, target_chat))
        await update.message.reply_text(
            "✅ تم بنجاح! 🎉\n"
            "• المجموعة اتنشأت\n"
            "• البوت اتضاف ومشرف\n"
            "• اليوزربوت شغال\n\n"
            "🎵 اكتب .الاوامر في أي جروب"
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        return BOT_TOKEN_USER


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 تم الإلغاء.")
    return ConversationHandler.END


async def manual_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ادخل توكن البوت:")
    return BOT_TOKEN_USER


# ══════════════════════════════════════════
# إنشاء المجموعة
# ══════════════════════════════════════════
async def create_and_setup_group(client, bot_token):
    bot = Bot(token=bot_token)
    bot_info = await bot.get_me()

    result = await client(CreateChannelRequest(
        title="🎵 تيلثون تـلـاشـاني",
        about="مجموعة اليوزربوت 🎧",
        megagroup=True
    ))
    group_id = result.chats[0].id
    access_hash = result.chats[0].access_hash
    group_peer = InputPeerChannel(group_id, access_hash)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://i.postimg.cc/VNvHmGd0/Picsart-25-08-27-23-50-22-266.jpg") as resp:
                if resp.status == 200:
                    data = await resp.read()
                    up = await client.upload_file(data, file_name="photo.jpg")
                    await client(EditPhotoRequest(channel=group_peer, photo=InputChatUploadedPhoto(file=up)))
    except Exception as e:
        logger.warning(f"Photo error: {e}")

    await client(InviteToChannelRequest(channel=group_peer, users=[bot_info.username]))
    bot_entity = await client.get_entity(bot_info.username)
    await client(EditAdminRequest(
        channel=group_peer,
        user_id=bot_entity.id,
        admin_rights=ChatAdminRights(
            post_messages=True, edit_messages=True, delete_messages=True,
            ban_users=True, invite_users=True, pin_messages=True,
            change_info=True, manage_call=True, add_admins=False
        ),
        rank="مشرف تلقائي"
    ))
    return group_id


# ══════════════════════════════════════════
# اليوزربوت
# ══════════════════════════════════════════
async def start_userbot(client, target_chat):
    me = await client.get_me()
    owner_id = me.id
    logger.info(f"Userbot: {me.first_name}")
    print(f"\n✅ اليوزربوت شغال: {me.first_name}\n")

    @client.on(events.NewMessage)
    async def handler(event):
        text = (event.raw_text or "").strip()
        is_owner = event.sender_id == owner_id
        is_group = event.is_group

        # ══ أوامر الموسيقى — للكل في الجروبات ══
        if is_group:

            if text.lower().startswith(".play") or text.startswith(".شغل"):
                args = text.split(maxsplit=1)
                query = args[1].strip() if len(args) > 1 else ""
                if not query:
                    await event.respond("⚠️ استخدم: .play <اسم الأغنية أو رابط>")
                    return
                msg = await event.respond("🔍 جاري البحث والتحميل...")
                try:
                    file_path, title, duration = await search_and_download(query, event.chat_id)
                    player = get_player(event.chat_id)
                    sender = await event.get_sender()
                    track = {"title": title, "duration": duration, "file": file_path, "requested_by": sender.first_name}

                    if player["current"] is None:
                        player["queue"].append(track)
                        player["current"] = track
                        await pytgcalls.join_group_call(
                            event.chat_id,
                            MediaStream(file_path),
                        )
                        await msg.edit(f"🎵 بيشتغل:\n🎧 {title}\n⏱ {duration}\n👤 {sender.first_name}")
                    else:
                        player["queue"].append(track)
                        await msg.edit(f"✅ في القايمة:\n🎧 {title}\n📍 الترتيب: {len(player['queue'])}")
                except Exception as e:
                    logger.error(f".play error: {e}")
                    await msg.edit(f"❌ خطأ: {e}")
                return

            if text in (".pause", ".وقف"):
                try:
                    await pytgcalls.pause_stream(event.chat_id)
                    await event.respond("⏸ تم الإيقاف المؤقت")
                except Exception as e:
                    await event.respond(f"❌ {e}")
                return

            if text in (".resume", ".كمل"):
                try:
                    await pytgcalls.resume_stream(event.chat_id)
                    await event.respond("▶️ تم الاستئناف")
                except Exception as e:
                    await event.respond(f"❌ {e}")
                return

            if text in (".skip", ".تخطي"):
                player = get_player(event.chat_id)
                try:
                    if player["queue"]:
                        player["queue"].pop(0)
                    if player["queue"]:
                        nxt = player["queue"][0]
                        player["current"] = nxt
                        await pytgcalls.change_stream(event.chat_id, MediaStream(nxt["file"]))
                        await event.respond(f"⏭ التالية:\n🎧 {nxt['title']}")
                    else:
                        player["current"] = None
                        await pytgcalls.leave_group_call(event.chat_id)
                        cleanup_downloads(event.chat_id)
                        await event.respond("⏹ خلصت القايمة!")
                except Exception as e:
                    await event.respond(f"❌ {e}")
                return

            if text in (".stop", ".ستوب"):
                player = get_player(event.chat_id)
                try:
                    await pytgcalls.leave_group_call(event.chat_id)
                    player["queue"].clear()
                    player["current"] = None
                    cleanup_downloads(event.chat_id)
                    await event.respond("⏹ تم الإيقاف")
                except Exception as e:
                    await event.respond(f"❌ {e}")
                return

            if text in (".queue", ".قايمة", ".q"):
                player = get_player(event.chat_id)
                if not player["queue"]:
                    await event.respond("📋 القايمة فاضية!")
                    return
                lines = ["🎵 قايمة الأغاني:"]
                for i, t in enumerate(player["queue"]):
                    lines.append(f"{'▶️' if i==0 else f'{i+1}.'} {t['title']} | {t['duration']}")
                await event.respond("\n".join(lines))
                return

            if text in (".loop", ".تكرار"):
                player = get_player(event.chat_id)
                player["loop"] = not player["loop"]
                await event.respond(f"🔁 التكرار: {'شغّال' if player['loop'] else 'مطفي'}")
                return

            if text in (".now", ".np", ".الحالية"):
                player = get_player(event.chat_id)
                if player["current"]:
                    t = player["current"]
                    await event.respond(f"🎧 الحالية:\n🎵 {t['title']}\n⏱ {t['duration']}\n🔁 {'تكرار' if player['loop'] else 'بدون تكرار'}")
                else:
                    await event.respond("📭 مفيش أغنية شغّالة")
                return

        # ══ تحويل الرسايل الخاصة ══
        if not is_owner:
            if event.incoming and event.is_private:
                try:
                    sender = await event.get_sender()
                    name = getattr(sender, "first_name", "مجهول")
                    uname = getattr(sender, "username", None)
                    caption = f"📩 من {name} (@{uname or 'لا يوجد'}):\n{event.raw_text or ''}"
                    if event.media:
                        await client.send_file(target_chat, event.media, caption=caption)
                    else:
                        await client.send_message(target_chat, caption)
                except Exception as e:
                    logger.error(f"forward error: {e}")
            return

        # ══ أوامر المالك ══
        if text == ".الاوامر":
            await event.respond(
                "📌 أوامر تيلثون تـلـاشـاني\n"
                "━━━━━━━━━━━━━━━\n"
                "🎵 الموسيقى (للجميع):\n"
                ".play <اسم/رابط> — شغّل\n"
                ".pause / .resume — وقّف/كمّل\n"
                ".skip — التالية\n"
                ".stop — وقّف كل شيء\n"
                ".queue — القايمة\n"
                ".loop — تكرار\n"
                ".now — الحالية\n"
                "━━━━━━━━━━━━━━━\n"
                "👤 عامة:\n"
                ".تغييرالاسم <اسم>\n"
                ".معلومات | .حالة\n"
                ".رسالة @يوزر <نص>\n"
                ".كشف (رد) | .حذف (رد)\n"
                ".حذفكل | .ايقاف\n"
                "━━━━━━━━━━━━━━━\n"
                "👥 جروبات (مشرف):\n"
                ".حظر | .فكحظر\n"
                ".كتم | .فككتم\n"
                ".اضافة @يوزر\n"
                ".وصف <نص>\n"
                ".صورةمجموعة (رد على صورة)"
            )

        elif text.startswith(".تغييرالاسم "):
            try:
                await client(UpdateProfileRequest(first_name=text.split(maxsplit=1)[1]))
                await event.respond("✅ تم تغيير الاسم")
            except Exception as e:
                await event.respond(f"❌ {e}")

        elif text == ".معلومات":
            me_info = await client.get_me()
            await event.respond(f"📋 الاسم: {me_info.first_name}\nالمعرف: @{me_info.username or 'لا يوجد'}\nID: {me_info.id}")

        elif text == ".حالة":
            await event.respond("✅ اليوزربوت شغال! 🚀")

        elif text.startswith(".رسالة "):
            parts = text.split(maxsplit=2)
            if len(parts) >= 3:
                try:
                    u = await client.get_entity(parts[1].strip("@"))
                    await client.send_message(u, parts[2])
                    await event.respond("✅ تم الإرسال")
                except Exception as e:
                    await event.respond(f"❌ {e}")

        elif text.startswith(".كشف"):
            if event.is_reply:
                reply = await event.get_reply_message()
                try:
                    u = await client.get_entity(reply.sender_id)
                    await event.respond(f"📋 {u.first_name}\n@{getattr(u,'username',None) or 'لا يوجد'}\nID: {u.id}")
                except Exception as e:
                    await event.respond(f"❌ {e}")
            else:
                await event.respond("⚠️ رد على رسالة")

        elif text == ".حذفكل":
            try:
                msgs = await client.get_messages(event.chat_id, limit=100)
                await client.delete_messages(event.chat_id, [m.id for m in msgs])
            except Exception as e:
                await event.respond(f"❌ {e}")

        elif text.startswith(".حذف"):
            if event.is_reply:
                reply = await event.get_reply_message()
                try:
                    await client.delete_messages(event.chat_id, [reply.id])
                except Exception as e:
                    await event.respond(f"❌ {e}")
            else:
                await event.respond("⚠️ رد على رسالة")

        elif text == ".ايقاف":
            await event.respond("🛑 جاري الإيقاف...")
            if pyro_client:
                await pyro_client.stop()
            await client.disconnect()

        if is_group and is_owner:
            if text.startswith(".حظر"):
                target = await _resolve(client, event, text)
                if target:
                    try:
                        await client.edit_permissions(event.chat_id, target, view_messages=False)
                        await event.respond("🚫 تم الحظر!")
                    except ChatAdminRequiredError:
                        await event.respond("❌ لازم تكون مشرف!")
                    except Exception as e:
                        await event.respond(f"❌ {e}")

            elif text.startswith(".فكحظر"):
                target = await _resolve(client, event, text)
                if target:
                    try:
                        await client.edit_permissions(event.chat_id, target, view_messages=True)
                        await event.respond("✅ تم فك الحظر!")
                    except ChatAdminRequiredError:
                        await event.respond("❌ لازم تكون مشرف!")
                    except Exception as e:
                        await event.respond(f"❌ {e}")

            elif text.startswith(".كتم"):
                target = await _resolve(client, event, text)
                if target:
                    try:
                        await client.edit_permissions(event.chat_id, target, send_messages=False)
                        await event.respond("🔇 تم الكتم!")
                    except ChatAdminRequiredError:
                        await event.respond("❌ لازم تكون مشرف!")
                    except Exception as e:
                        await event.respond(f"❌ {e}")

            elif text.startswith(".فككتم"):
                target = await _resolve(client, event, text)
                if target:
                    try:
                        await client.edit_permissions(event.chat_id, target, send_messages=True)
                        await event.respond("✅ تم فك الكتم!")
                    except ChatAdminRequiredError:
                        await event.respond("❌ لازم تكون مشرف!")
                    except Exception as e:
                        await event.respond(f"❌ {e}")

            elif text.startswith(".اضافة "):
                uname = text.split(maxsplit=1)[1].strip("@")
                try:
                    u = await client.get_entity(uname)
                    await client(InviteToChannelRequest(event.chat_id, [u]))
                    await event.respond(f"✅ تم إضافة @{uname}")
                except Exception as e:
                    await event.respond(f"❌ {e}")

            elif text.startswith(".وصف "):
                try:
                    await client(EditChatAboutRequest(peer=event.chat_id, about=text.split(maxsplit=1)[1]))
                    await event.respond("✅ تم تغيير الوصف!")
                except Exception as e:
                    await event.respond(f"❌ {e}")

            elif text.startswith(".صورةمجموعة") and event.is_reply:
                reply = await event.get_reply_message()
                if reply.photo:
                    try:
                        path = await client.download_media(reply.photo)
                        up = await client.upload_file(path)
                        await client(EditPhotoRequest(channel=event.chat_id, photo=InputChatUploadedPhoto(file=up)))
                        await event.respond("✅ تم تغيير الصورة!")
                        os.remove(path)
                    except Exception as e:
                        await event.respond(f"❌ {e}")
                else:
                    await event.respond("⚠️ رد على صورة!")

    try:
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Userbot error: {e}")
        if pyro_client:
            try:
                await pyro_client.stop()
            except Exception:
                pass


async def _resolve(client, event, text):
    args = text.split()
    if len(args) > 1:
        try:
            u = await client.get_entity(args[1].strip("@"))
            return u.id
        except Exception as e:
            await event.respond(f"❌ {e}")
            return None
    elif event.is_reply:
        return (await event.get_reply_message()).sender_id
    else:
        await event.respond("⚠️ استخدم مع @يوزر أو رد")
        return None


# ══════════════════════════════════════════
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
        API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        CODE_DIGITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code_digits)],
        PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        BOT_TOKEN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)],
    },
    fallbacks=[CommandHandler("cancel", cancel), CommandHandler("token", manual_token)]
)

MAIN_BOT_TOKEN = "8594715948:AAGnvPK5O1TkHvm-bVoL5ehua6Do9L4J4_4"

if __name__ == "__main__":
    print("✅ البوت شغال... ابعت /start\n")
    app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()
    app.add_handler(conv_handler)
    app.run_polling()