#!/usr/bin/env python3
# main.py - مصنع الجلسات المطور
# تم التعديل: فبراير 2026

import os
import asyncio
import logging
import json
import aiohttp
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest, InviteToChannelRequest, EditAdminRequest
from telethon.tl.types import InputChatUploadedPhoto, InputPeerChannel, ChatAdminRights
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from userbot import start_userbot

# ==================== إعدادات التسجيل ====================
logging.basicConfig(
    filename='userbot_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==================== الثوابت ====================
# مراحل المحادثة
API_ID_STATE, API_HASH_STATE, PHONE_STATE, CODE_STATE, PASSWORD_STATE, BOT_TOKEN_STATE = range(6)

# ==================== الإعدادات الرئيسية من .env ====================
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "")
STARTUP_IMAGE_URL = os.getenv("STARTUP_IMAGE", "https://i.postimg.cc/wxV3PspQ/1756574872401.gif")
DEFAULT_GROUP_PHOTO_URL = os.getenv("DEFAULT_GROUP_PHOTO", "https://i.postimg.cc/VNvHmGd0/Picsart-25-08-27-23-50-22-266.jpg")

# التحقق من الإعدادات الأساسية
if not MAIN_BOT_TOKEN:
    raise ValueError("❌ MAIN_BOT_TOKEN مش موجود في ملف .env!")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID مش موجود في ملف .env!")

# ==================== المسارات ====================
USERS_FILE = "users.json"
SESSIONS_DIR = "sessions"
CONFIG_FILE = "config.json"

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

# ==================== التخزين (كل مستخدم ليه dict خاص بيه) ====================
# ✅ الإصلاح: بدل user_data_store مشترك، كل مستخدم ليه dict خاص
users_sessions_data = {}   # {user_id: {api_id, api_hash, phone, client, ...}}
admin_actions = {}
active_userbots = {}

# ==================== رموز التزيين ====================
DECOR_SUCCESS = "✦"
DECOR_ERROR = "✘"
DECOR_CANCEL = "✗"
DECOR_SESSIONS = "⎙"
DECOR_BROADCAST = "📣"
DECOR_STATS = "📊"
DECOR_SUBSCRIPTION = "🔒"
DECOR_IMAGE = "🖼"
DECOR_CHECK = "✔"
DECOR_DELETE = "✖"
DECOR_CODE = "🔢"
DECOR_TOKEN = "⚷"
DECOR_PHONE = "☏"
DECOR_FRAME = "━─━"
DECOR_TITLE = f"{DECOR_FRAME} {{}} {DECOR_FRAME}"

# ==================== الإعدادات الافتراضية ====================
DEFAULT_CONFIG = {
    "FORCE_CHANNELS": [],
    "SUBSCRIPTION_IMAGE": DEFAULT_GROUP_PHOTO_URL,
    "STARTUP_IMAGE": STARTUP_IMAGE_URL,
    "GROUP_PHOTO": DEFAULT_GROUP_PHOTO_URL,   # ✅ صورة المجموعة اللي بتتعمل
    "BOT_ENABLED": True,
    "MAX_SESSIONS": int(os.getenv("MAX_SESSIONS", "50"))
}

# ==================== الإعدادات ====================
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception as e:
        logging.warning(f"فشل تحميل الإعدادات: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"فشل حفظ الإعدادات: {e}")

config = load_config()

# ==================== حفظ/تحميل بيانات الجلسة ====================
def save_session_data(phone, api_id, api_hash, bot_token, target_chat):
    """✅ الإصلاح: نحفظ api_id و api_hash مع كل جلسة"""
    session_data_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.json")
    data = {
        "bot_token": bot_token,
        "target_chat": target_chat,
        "phone": phone,
        "api_id": api_id,       # ✅ مهم جداً لإعادة التشغيل
        "api_hash": api_hash,   # ✅ مهم جداً لإعادة التشغيل
        "created_at": datetime.now().isoformat()
    }
    try:
        with open(session_data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ تم حفظ بيانات الجلسة: {phone}")
    except Exception as e:
        logging.error(f"❌ فشل حفظ بيانات الجلسة {phone}: {e}")

def load_session_data(phone):
    session_data_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.json")
    if os.path.exists(session_data_file):
        try:
            with open(session_data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"❌ فشل تحميل بيانات الجلسة {phone}: {e}")
    return None

# ==================== وظائف مساعدة ====================
def is_valid_api_id(api_id: str) -> bool:
    return api_id.isdigit() and len(api_id) >= 4

def is_valid_api_hash(api_hash: str) -> bool:
    return len(api_hash) == 32 and api_hash.isalnum()

def save_user(user_id: int):
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = []
    if user_id not in users:
        users.append(user_id)
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False)
        except Exception as e:
            logging.error(f"❌ فشل حفظ المستخدم: {e}")

def get_user_store(user_id: int) -> dict:
    """✅ الإصلاح: جيب أو أنشئ dict خاص بكل مستخدم"""
    if user_id not in users_sessions_data:
        users_sessions_data[user_id] = {}
    return users_sessions_data[user_id]

def clear_user_store(user_id: int):
    """امسح بيانات مستخدم معين"""
    if user_id in users_sessions_data:
        # قفل الكلاينت - بس من غير create_task لأننا في sync context
        store = users_sessions_data[user_id]
        if 'client' in store:
            try:
                client = store['client']
                if client.is_connected():
                    # نستخدم loop مباشرة لو موجودة
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(client.disconnect())
                        else:
                            loop.run_until_complete(client.disconnect())
                    except Exception:
                        pass
            except Exception:
                pass
        del users_sessions_data[user_id]

async def check_force_sub(user_id: int, bot: Bot) -> bool:
    channels = config.get("FORCE_CHANNELS", [])
    if not channels:
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            logging.warning(f"⚠️ فشل التحقق من الاشتراك في {channel}: {e}")
            return False
    return True

def check_session_limit() -> tuple[bool, int, int]:
    """✅ جديد: تحقق من الحد الأقصى للجلسات"""
    max_sessions = config.get("MAX_SESSIONS", 50)
    current_sessions = len([f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    return current_sessions < max_sessions, current_sessions, max_sessions

async def delete_previous_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        if "last_message_id" in context.user_data:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["last_message_id"])
            del context.user_data["last_message_id"]
    except Exception:
        pass

async def send_clean(context, chat_id: int, text: str, reply_markup=None, parse_mode=None) -> int:
    """✅ بتحذف الرسالة القديمة وتبعت جديدة - يحافظ على الشات نضيف"""
    # حذف الرسالة القديمة
    try:
        if "last_message_id" in context.user_data:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["last_message_id"])
            del context.user_data["last_message_id"]
    except Exception:
        pass
    # بعت الجديدة
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
    context.user_data["last_message_id"] = msg.message_id
    return msg.message_id

async def edit_admin_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str,
                             reply_markup=None, photo=None, parse_mode=None):
    try:
        if "admin_message_id" in context.user_data:
            try:
                if photo:
                    await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["admin_message_id"])
                    msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text,
                                                       reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    msg = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=context.user_data["admin_message_id"],
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                context.user_data["admin_message_id"] = msg.message_id
                return msg
            except Exception:
                pass

        if photo:
            msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text,
                                               reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            msg = await context.bot.send_message(chat_id=chat_id, text=text,
                                                 reply_markup=reply_markup, parse_mode=parse_mode)
        context.user_data["admin_message_id"] = msg.message_id
        return msg
    except Exception as e:
        logging.error(f"❌ خطأ في إرسال/تعديل رسالة الأدمن: {e}")
        return None

# ==================== إشعار الأدمن ====================
def admin_main_keyboard(bot_enabled, max_sessions, active_count):
    """✅ لوحة الأدمن الرئيسية - أقسام"""
    toggle_text = "🔴 تعطيل البوت" if bot_enabled else "🟢 تفعيل البوت"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="sec_stats"),
            InlineKeyboardButton("📣 الإذاعة",     callback_data="sec_broadcast"),
        ],
        [
            InlineKeyboardButton("⎙ الجلسات",     callback_data="sec_sessions"),
            InlineKeyboardButton("🔒 الاشتراك",   callback_data="sec_sub"),
        ],
        [
            InlineKeyboardButton("🖼 صورة المجموعة", callback_data="sec_groupphoto"),
        ],
        [
            InlineKeyboardButton(toggle_text,      callback_data="toggle_bot"),
        ],
    ])

def back_btn():
    """زر الرجوع للوحة الرئيسية"""
    return InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")

async def show_section(query, text: str, keyboard):
    """✅ عرض قسم - يعدل caption لو صورة، أو edit_text لو نص"""
    if isinstance(keyboard, InlineKeyboardMarkup):
        kb = keyboard
    else:
        kb = InlineKeyboardMarkup(keyboard)
    # جرب تعدل الـ caption (لو صورة/animation)
    try:
        await query.message.edit_caption(caption=text, reply_markup=kb)
        return
    except Exception:
        pass
    # جرب تعدل النص
    try:
        await query.message.edit_text(text, reply_markup=kb)
        return
    except Exception:
        pass
    # آخر حل: رسالة جديدة
    await query.message.reply_text(text, reply_markup=kb)

async def notify_admin_session(phone: str, user_id: int, session_file: str):
    keyboard = [[
        InlineKeyboardButton(f"{DECOR_CHECK} السماح", callback_data=f"allow|{session_file}"),
        InlineKeyboardButton(f"{DECOR_DELETE} الحذف", callback_data=f"delete_session|{session_file}")
    ]]
    text = (f"{DECOR_TITLE.format('جلسة جديدة')}\n\n"
            f"{DECOR_PHONE} الرقم: {phone}\n"
            f"{DECOR_TOKEN} المستخدم: {user_id}\n"
            f"{DECOR_SESSIONS} الملف: {session_file}")
    try:
        await Bot(token=MAIN_BOT_TOKEN).send_message(
            ADMIN_ID, text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logging.error(f"❌ فشل إشعار المطور: {e}")

async def notify_admin_session_down(phone: str):
    """✅ جديد: إشعار الأدمن لما جلسة تنقطع"""
    try:
        text = (f"⚠️ {DECOR_TITLE.format('جلسة انقطعت')}\n\n"
                f"{DECOR_PHONE} الرقم: {phone}\n"
                f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        await Bot(token=MAIN_BOT_TOKEN).send_message(ADMIN_ID, text)
    except Exception as e:
        logging.error(f"❌ فشل إشعار انقطاع الجلسة: {e}")

# ==================== رسائل الترحيب ====================
async def send_disabled_message(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """✅ جديد: رسالة التعطيل مع صورة بروفايل المطور وزر الشات"""
    try:
        # جيب صورة البروفايل والاسم من تليجرام
        dev_photos = await context.bot.get_user_profile_photos(ADMIN_ID, limit=1)
        dev_chat = await context.bot.get_chat(ADMIN_ID)
        dev_name = dev_chat.first_name or "المطور"
        dev_username = dev_chat.username

        caption = (
            f"🔴 البوت معطل حالياً\n\n"
            f"للاستفسار تواصل مع المطور\n"
            f"👤 {dev_name}"
        )

        # زر الشات المباشر مع المطور
        if dev_username:
            url = f"https://t.me/{dev_username}"
        else:
            url = f"tg://user?id={ADMIN_ID}"

        keyboard = [[InlineKeyboardButton(f"💬 تواصل مع {dev_name}", url=url)]]
        markup = InlineKeyboardMarkup(keyboard)

        # لو عنده صورة بروفايل نبعتها
        if dev_photos and dev_photos.photos:
            photo_id = dev_photos.photos[0][-1].file_id
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=context.user_data.get("last_message_id", 0))
            except Exception:
                pass
            msg = await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=caption,
                reply_markup=markup
            )
        else:
            # لو مفيش صورة نبعت نص عادي
            msg = await context.bot.send_message(
                chat_id=user_id,
                text=caption,
                reply_markup=markup
            )
        context.user_data["last_message_id"] = msg.message_id

    except Exception as e:
        logging.error(f"❌ خطأ في send_disabled_message: {e}")
        # fallback: رسالة نص بسيطة
        try:
            msg = await context.bot.send_message(
                chat_id=user_id,
                text=f"🔴 البوت معطل حالياً\n\nتواصل مع المطور",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 تواصل مع المطور", url=f"tg://user?id={ADMIN_ID}")
                ]])
            )
            context.user_data["last_message_id"] = msg.message_id
        except Exception:
            pass

async def get_channel_title(bot: Bot, channel: str) -> str:
    """✅ جديد: جيب الاسم الحقيقي للقناة من تيليجرام"""
    try:
        chat = await bot.get_chat(channel)
        return chat.title or channel
    except Exception:
        return channel

async def send_subscription_prompt(bot: Bot, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    channels = config.get("FORCE_CHANNELS", [])
    img = config.get("SUBSCRIPTION_IMAGE")
    buttons = []
    for ch in channels:
        chname = ch.strip("@")
        # ✅ التعديل: جيب الاسم الحقيقي من تيليجرام
        title = await get_channel_title(bot, ch)
        buttons.append(InlineKeyboardButton(f"📣 {title}", url=f"https://t.me/{chname}"))
    buttons.append(InlineKeyboardButton(f"{DECOR_CHECK} تحقق من الاشتراك", callback_data="force_joincheck"))

    rows = [[b] for b in buttons]
    caption = f"{DECOR_SUBSCRIPTION} يجب الاشتراك في القنوات التالية لاستخدام البوت {DECOR_SUBSCRIPTION}"

    await delete_previous_message(context, user_id)
    try:
        msg = await bot.send_photo(chat_id=user_id, photo=img, caption=caption, reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        msg = await bot.send_message(chat_id=user_id, text=caption, reply_markup=InlineKeyboardMarkup(rows))
    context.user_data["last_message_id"] = msg.message_id

async def send_welcome_message(update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update, 'effective_user'):
        user_id = update.effective_user.id
    elif hasattr(update, 'from_user'):
        user_id = update.from_user.id
    else:
        return

    img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
    caption = f"{DECOR_TITLE.format('مرحباً بك')}\n\n✨ اضغط ابدأ لتنصيب تيليثون {DECOR_SUCCESS}"
    buttons = [[InlineKeyboardButton(f"{DECOR_SUCCESS} ابدأ الآن", callback_data="start_now")]]

    await delete_previous_message(context, user_id)
    sent = False
    # جرب animation
    if img:
        try:
            msg = await context.bot.send_animation(chat_id=user_id, animation=img, caption=caption,
                                                    reply_markup=InlineKeyboardMarkup(buttons))
            sent = True
        except Exception:
            pass
    # لو فشلت جرب صورة
    if not sent and img:
        try:
            msg = await context.bot.send_photo(chat_id=user_id, photo=img, caption=caption,
                                               reply_markup=InlineKeyboardMarkup(buttons))
            sent = True
        except Exception:
            pass
    # لو فشلت ابعت نص
    if not sent:
        msg = await context.bot.send_message(chat_id=user_id, text=caption,
                                              reply_markup=InlineKeyboardMarkup(buttons))
    context.user_data["last_message_id"] = msg.message_id

# ==================== إنشاء البوت تلقائياً ====================
async def check_existing_bot(client: TelegramClient) -> dict:
    try:
        botfather = await client.get_entity('BotFather')
        await client.send_message(botfather, '/mybots')
        await asyncio.sleep(2)
        messages = await client.get_messages(botfather, limit=1)
        if messages and messages[0].reply_markup:
            buttons = messages[0].reply_markup.rows
            if buttons and len(buttons) > 0:
                bot_button = buttons[0].buttons[0]
                bot_username = bot_button.text.strip('@')
                await client.send_message(botfather, f'@{bot_username}')
                await asyncio.sleep(2)
                await client.send_message(botfather, '/token')
                await asyncio.sleep(2)
                token_messages = await client.get_messages(botfather, limit=1)
                if token_messages and token_messages[0].text:
                    text = token_messages[0].text
                    if ':' in text:
                        for line in text.split('\n'):
                            if ':' in line and 'AAH' in line:
                                return {'exists': True, 'token': line.strip(), 'username': bot_username}
        return {'exists': False}
    except Exception as e:
        logging.error(f"❌ خطأ في التحقق من البوت الموجود: {e}")
        return {'exists': False}

async def create_bot_automatically(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✅ التعديل: مش بيعمل بوت لوحده - بيطلب من المستخدم يعمل من BotFather"""
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id if update.callback_query else user_id

    text = (
        f"{DECOR_TOKEN} الخطوة الأخيرة!\n\n"
        f"1️⃣ افتح @BotFather\n"
        f"2️⃣ ابعت /newbot\n"
        f"3️⃣ اكتب اسم للبوت\n"
        f"4️⃣ اكتب يوزر للبوت (لازم ينتهي بـ bot)\n"
        f"5️⃣ انسخ التوكن وابعته هنا\n\n"
        f"⚡ ابعت التوكن هنا بعد ما تخلص:"
    )
    await send_clean(context, chat_id, text)
    return BOT_TOKEN_STATE

async def create_and_setup_group(client: TelegramClient, bot_token: str):
    try:
        bot = Bot(token=bot_token)
        bot_info = await bot.get_me()
        bot_username = bot_info.username or str(bot_info.id)
    except Exception as e:
        raise Exception(f"{DECOR_ERROR} توكن غير صالح: {e}")

    group_title = "مجموعة تيليثون تلاشاني"
    group_about = """
╭━─━─━Source━─━─━➾

                @I0_I6

╞═⟃══TALASHNY══⟄═╡

          تم التنصيب بنجاح .     

╰━─━─━Source━─━─━➾"""

    try:
        result = await client(CreateChannelRequest(title=group_title, about=group_about, megagroup=True))
        group = result.chats[0]
        group_id = group.id
        group_peer = InputPeerChannel(group_id, group.access_hash)
    except Exception as e:
        raise Exception(f"{DECOR_ERROR} فشل إنشاء المجموعة: {e}")

    try:
        photo_source = config.get("GROUP_PHOTO", DEFAULT_GROUP_PHOTO_URL)
        photo_bytes = None

        if photo_source.startswith("http://") or photo_source.startswith("https://"):
            # رابط URL - نحمله
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_source) as resp:
                    if resp.status == 200:
                        photo_bytes = await resp.read()
        elif os.path.exists(photo_source):
            # ملف محلي - نقرأه مباشرة
            with open(photo_source, "rb") as f:
                photo_bytes = f.read()

        if photo_bytes:
            uploaded_photo = await client.upload_file(photo_bytes, file_name="group_photo.jpg")
            await client(EditPhotoRequest(channel=group_peer, photo=InputChatUploadedPhoto(file=uploaded_photo)))
    except Exception as e:
        logging.error(f"❌ فشل تعيين صورة المجموعة: {e}")

    try:
        await client(InviteToChannelRequest(channel=group_peer, users=[bot_username]))
        await asyncio.sleep(1)
        bot_entity = await client.get_entity(bot_username)
        admin_rights = ChatAdminRights(
            post_messages=True, edit_messages=True, delete_messages=True,
            ban_users=True, invite_users=True, pin_messages=True,
            change_info=True, manage_call=True
        )
        await client(EditAdminRequest(channel=group_peer, user_id=bot_entity.id,
                                      admin_rights=admin_rights, rank="مشرف"))
    except Exception as e:
        logging.warning(f"⚠️ فشل إضافة/ترقية البوت: {e}")

    # نرجع الـ ID مع علامة سالب عشان يكون supergroup ID صح
    return int(f"-100{group_id}")

# ==================== Keep Alive ====================
async def keep_alive_monitor(phone: str):
    """✅ مراقبة الاتصال مع إشعار الأدمن لما تنقطع"""
    was_connected = True
    while phone in active_userbots:
        try:
            client = active_userbots[phone]['client']
            if not client.is_connected():
                logging.warning(f"⚠️ انقطع الاتصال للجلسة {phone}، جاري إعادة الاتصال...")
                if was_connected:
                    await notify_admin_session_down(phone)
                    was_connected = False
                await client.connect()
                if await client.is_user_authorized():
                    logging.info(f"✅ تم إعادة الاتصال للجلسة {phone}")
                    was_connected = True
                else:
                    logging.error(f"❌ الجلسة {phone} غير مصرح بها")
                    break
            else:
                was_connected = True
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"❌ خطأ في keep-alive للجلسة {phone}: {e}")
            await asyncio.sleep(60)

# ==================== إعادة تشغيل الجلسات ====================
async def restart_userbots():
    """✅ الإصلاح: كل جلسة تستخدم api_id/api_hash المحفوظ معها"""
    logging.info(f"{DECOR_SUCCESS} بدء إعادة تشغيل اليوزربوتات...")
    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]

    if not session_files:
        logging.info("ℹ️ لا توجد جلسات لإعادة تشغيلها")
        return

    for session_file in session_files:
        phone = session_file.replace('.session', '')
        session_path = os.path.join(SESSIONS_DIR, session_file)
        session_data = load_session_data(phone)

        if not session_data:
            logging.warning(f"⚠️ لا توجد بيانات للجلسة: {phone}")
            continue

        bot_token = session_data.get('bot_token')
        api_id = session_data.get('api_id')
        api_hash = session_data.get('api_hash')

        if not all([bot_token, api_id, api_hash]):
            logging.warning(f"⚠️ بيانات ناقصة للجلسة: {phone}")
            continue

        client = TelegramClient(session_path, api_id, api_hash)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logging.warning(f"⚠️ الجلسة غير مصرح بها: {phone}")
                await client.disconnect()
                continue

            try:
                bot = Bot(token=bot_token)
                bot_info = await bot.get_me()
                logging.info(f"✅ توكن صالح: @{bot_info.username}")
            except Exception as e:
                logging.error(f"❌ توكن غير صالح للجلسة {phone}: {e}")
                await client.disconnect()
                continue

            temp_store = {'client': client, 'phone': phone, 'bot_token': bot_token, 'target_chat': None}
            task = asyncio.create_task(start_userbot(client, None, temp_store))
            monitor_task = asyncio.create_task(keep_alive_monitor(phone))

            active_userbots[phone] = {
                'client': client, 'task': task,
                'monitor_task': monitor_task, 'target_chat': None
            }
            logging.info(f"✅ تم تشغيل اليوزربوت: {phone}")
            print(f"✅ تيلثون شغال على: {phone}")

        except Exception as e:
            logging.error(f"❌ فشل إعادة تشغيل الجلسة {phone}: {e}")
            if client.is_connected():
                await client.disconnect()

    logging.info(f"{DECOR_SUCCESS} اكتملت إعادة التشغيل ({len(active_userbots)} نشط)")

# ==================== معالجات المحادثة ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    clear_user_store(user_id)
    
    # ✅ احفظ last_message_id قبل ما تعمل clear
    last_msg_id = context.user_data.get("last_message_id")
    context.user_data.clear()
    if last_msg_id:
        context.user_data["last_message_id"] = last_msg_id

    # ✅ حذف رسالة /start اللي المستخدم بعتها
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    if user_id == ADMIN_ID:
        img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
        bot_enabled = config.get("BOT_ENABLED", True)
        max_sessions = config.get("MAX_SESSIONS", 50)
        current_sessions = len([f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
        bot_status = f"مفعّل {DECOR_SUCCESS}" if bot_enabled else f"معطل {DECOR_CANCEL}"
        caption = (f"{DECOR_TITLE.format('لوحة تحكم المطور')}\n\n"
                   f"{DECOR_SUCCESS} حالة البوت: {bot_status}\n"
                   f"{DECOR_STATS} اليوزربوتات النشطة: {len(active_userbots)}\n"
                   f"{DECOR_SESSIONS} الجلسات: {current_sessions}/{max_sessions}")

        toggle_text = f"🔴 تعطيل البوت" if bot_enabled else f"🟢 تفعيل البوت"
        # ✅ لوحة رئيسية بأقسام
        keyboard = [
            [
                InlineKeyboardButton(f"📊 الإحصائيات", callback_data="sec_stats"),
                InlineKeyboardButton(f"📣 الإذاعة", callback_data="sec_broadcast"),
            ],
            [
                InlineKeyboardButton(f"⎙ الجلسات", callback_data="sec_sessions"),
                InlineKeyboardButton(f"🔒 الاشتراك", callback_data="sec_sub"),
            ],
            [
                InlineKeyboardButton(toggle_text, callback_data="toggle_bot"),
            ],
        ]

        await edit_admin_message(context, user_id, caption,
                                  reply_markup=InlineKeyboardMarkup(keyboard), photo=img)
        return ConversationHandler.END

    if not config.get("BOT_ENABLED", True):
        await send_disabled_message(context, user_id)
        return ConversationHandler.END

    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return ConversationHandler.END

    # ✅ تحقق من الحد الأقصى قبل ما يبدأ
    can_add, current, max_s = check_session_limit()
    if not can_add:
        await send_clean(context, user_id, f"{DECOR_ERROR} البوت وصل الحد الأقصى من الجلسات ({current}/{max_s})\n\nتواصل مع المطور @I0_I6")
        return ConversationHandler.END

    await send_welcome_message(update, context)
    return ConversationHandler.END

async def start_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not config.get("BOT_ENABLED", True):
        await send_disabled_message(context, user_id)
        return ConversationHandler.END

    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return ConversationHandler.END

    # ✅ التعديل: الأدمن مش محدود بعدد الجلسات
    if user_id != ADMIN_ID:
        can_add, current, max_s = check_session_limit()
        if not can_add:
            await query.answer(f"وصل الحد الأقصى ({current}/{max_s})", show_alert=True)
            return ConversationHandler.END

    clear_user_store(user_id)
    await send_clean(context, user_id, f"{DECOR_TOKEN} أدخل API_ID بتاعك:\n\n📌 تقدر تجيبه من: my.telegram.org")
    return API_ID_STATE

async def create_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        return ConversationHandler.END

    clear_user_store(user_id)
    context.user_data.clear()
    
    # ✅ نبعت رسالة جديدة مباشرة على الشات
    msg = await query.message.reply_text(
        f"{DECOR_TOKEN} أدخل API_ID:\n\n📌 من: my.telegram.org"
    )
    context.user_data["last_message_id"] = msg.message_id
    return API_ID_STATE

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    api_id = update.message.text.strip()

    # ✅ حذف رسالة المستخدم فوراً (خصوصية)
    try:
        await update.message.delete()
    except Exception:
        pass

    if not is_valid_api_id(api_id):
        await send_clean(context, user_id, f"{DECOR_ERROR} API_ID يجب أن يكون أرقام فقط (4 أرقام أو أكتر)!")
        return API_ID_STATE

    store = get_user_store(user_id)
    store['api_id'] = int(api_id)

    await send_clean(context, user_id, f"{DECOR_TOKEN} ✅ API_ID اتحفظ!\n\nدلوقتي أدخل API_HASH:")
    return API_HASH_STATE

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    api_hash = update.message.text.strip()

    # ✅ حذف رسالة المستخدم فوراً (خصوصية)
    try:
        await update.message.delete()
    except Exception:
        pass

    if not is_valid_api_hash(api_hash):
        await send_clean(context, user_id, f"{DECOR_ERROR} API_HASH يجب أن يكون 32 حرف وأرقام!")
        return API_HASH_STATE

    store = get_user_store(user_id)
    store['api_hash'] = api_hash

    await send_clean(context, user_id, f"{DECOR_TOKEN} ✅ API_HASH اتحفظ!\n\n{DECOR_PHONE} أدخل رقم هاتفك مع كود الدولة:\nمثال: +201234567890")
    return PHONE_STATE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    phone = update.message.text.strip()

    # ✅ حذف رسالة المستخدم
    try:
        await update.message.delete()
    except Exception:
        pass

    store = get_user_store(user_id)
    store['phone'] = phone

    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")
    client = TelegramClient(session_file, store['api_id'], store['api_hash'])

    await client.connect()
    store['client'] = client

    # لو الجلسة موجودة ومصرح بيها
    session_data = load_session_data(phone)
    if session_data and await client.is_user_authorized():
        bot_token = session_data.get('bot_token')
        target_chat = session_data.get('target_chat')

        if bot_token and target_chat:
            try:
                bot = Bot(token=bot_token)
                await bot.get_me()

                await send_clean(context, user_id, f"{DECOR_CHECK} جلسة موجودة بالفعل!\n\nجاري إعادة التشغيل... {DECOR_SUCCESS}")

                temp_store = {'client': client, 'phone': phone, 'bot_token': bot_token, 'target_chat': target_chat}
                task = asyncio.create_task(start_userbot(client, target_chat, temp_store))
                monitor_task = asyncio.create_task(keep_alive_monitor(phone))
                active_userbots[phone] = {
                    'client': client, 'task': task,
                    'monitor_task': monitor_task, 'target_chat': target_chat
                }

                await send_clean(context, user_id, f"{DECOR_SUCCESS} تم إعادة تشغيل اليوزربوت بنجاح!\n\n")
                return ConversationHandler.END

            except Exception as e:
                logging.error(f"❌ التوكن المحفوظ غير صالح: {e}")
                return await create_bot_automatically(update, context)

    if await client.is_user_authorized():
        return await create_bot_automatically(update, context)

    try:
        await client.send_code_request(phone)
        await send_clean(context, user_id, f"{DECOR_CODE} تم إرسال كود التحقق!\n\n")
        return CODE_STATE
    except Exception as e:
        await send_clean(context, user_id, f"{DECOR_ERROR} خطأ في إرسال الكود: {str(e)}\n\nحاول مرة أخرى بإرسال /start")
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رقم رقم عشان تيليجرام مش بيحجبه"""
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    digit = update.message.text.strip()

    # ✅ حذف رسالة الرقم فوراً
    try:
        await update.message.delete()
    except Exception:
        pass

    if not digit.isdigit() or len(digit) != 1:
        await send_clean(context, user_id, f"{DECOR_ERROR} أدخل رقم واحد بس!")
        return CODE_STATE

    store = get_user_store(user_id)
    if 'code_digits' not in store:
        store['code_digits'] = []
    store['code_digits'].append(digit)

    # لو لسه ما اكتملناش
    if len(store['code_digits']) < 5:
        current = len(store['code_digits'])
        filled = "●" * current
        empty = "○" * (5 - current)
        await send_clean(context, user_id, f"{DECOR_CODE} {filled}{empty} ({current}/5)\n\nأدخل الرقم التالي:")
        return CODE_STATE

    code = "".join(store['code_digits'])
    store['code_digits'] = []  # مسح بعد الاستخدام
    client = store['client']
    phone = store['phone']
    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")

    try:
        await client.sign_in(phone=phone, code=code)
        await send_clean(context, user_id, f"{DECOR_CHECK} تم تسجيل الدخول بنجاح!\n\nجاري إعداد البوت... {DECOR_SUCCESS}")
        await notify_admin_session(phone, user_id, session_file)
        return await create_bot_automatically(update, context)

    except SessionPasswordNeededError:
        await send_clean(context, user_id, f"{DECOR_SUBSCRIPTION} الحساب محمي بكلمة مرور\n\nأدخل رمز التحقق بخطوتين (2FA):")
        return PASSWORD_STATE
    except Exception as e:
        error_text = str(e)
        # ✅ لو الكود انتهى، نبعت كود جديد تلقائياً
        if "expired" in error_text.lower() or "PHONE_CODE_EXPIRED" in error_text:
            try:
                store = get_user_store(user_id)
                await store['client'].send_code_request(store['phone'])
                await send_clean(context, user_id, f"⏰ الكود انتهت صلاحيته!\n\n{DECOR_CODE} تم إرسال كود جديد تلقائياً\n\n📲 أدخل الكود الجديد كامل مرة واحدة:")
                return CODE_STATE
            except Exception:
                msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{DECOR_ERROR} فشل إرسال كود جديد\n\nابعت /start وحاول تاني"
                )
                context.user_data["last_message_id"] = msg.message_id
                return ConversationHandler.END

        # أي خطأ تاني مع زر إعادة المحاولة
        keyboard = [[InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="start_now")]]
        msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"{DECOR_ERROR} فشل تسجيل الدخول\n\n{error_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    password = update.message.text.strip()
    store = get_user_store(user_id)
    client = store['client']
    phone = store['phone']
    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")

    # ✅ حذف رسالة الباسورد فوراً
    try:
        await update.message.delete()
    except Exception:
        pass

    try:
        await client.sign_in(password=password)
        await send_clean(context, user_id, f"{DECOR_CHECK} تم تسجيل الدخول بنجاح!\n\nجاري إعداد البوت... {DECOR_SUCCESS}")
        await notify_admin_session(phone, user_id, session_file)
        return await create_bot_automatically(update, context)

    except Exception as e:
        await send_clean(context, user_id, f"{DECOR_ERROR} كلمة المرور غير صحيحة\n\nحاول مرة أخرى:")
        return PASSWORD_STATE

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        return ConversationHandler.END

    bot_token = update.message.text.strip()

    # ✅ حذف رسالة التوكن فوراً
    try:
        await update.message.delete()
    except Exception:
        pass

    store = get_user_store(user_id)
    store['bot_token'] = bot_token

    try:
        bot = Bot(token=bot_token)
        await bot.get_me()
    except Exception as e:
        await send_clean(context, user_id, f"{DECOR_ERROR} توكن البوت غير صحيح!\n\nأرسل توكن صحيح من @BotFather {DECOR_TOKEN}")
        return BOT_TOKEN_STATE

    return await finalize_setup(update, context)

async def finalize_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id if update.callback_query else user_id
    store = get_user_store(user_id)

    try:
        client = store['client']
        bot_token = store['bot_token']
        phone = store['phone']
        api_id = store['api_id']
        api_hash = store['api_hash']

        await send_clean(context, chat_id, f"{DECOR_SUCCESS} جاري إنشاء المجموعة وإعداد البوت...\n\n⏳ قد يستغرق هذا بضع ثوان")

        target_chat = await create_and_setup_group(client, bot_token)
        store['target_chat'] = target_chat

        save_session_data(phone, api_id, api_hash, bot_token, target_chat)

        # target_chat بيتبعت None لـ start_userbot - المستخدم يربطه بأمر .تخزين
        temp_store = {'client': client, 'phone': phone, 'bot_token': bot_token, 'target_chat': None}
        task = asyncio.create_task(start_userbot(client, None, temp_store))
        monitor_task = asyncio.create_task(keep_alive_monitor(phone))

        active_userbots[phone] = {
            'client': client, 'task': task,
            'monitor_task': monitor_task, 'target_chat': None
        }

        await send_clean(context, chat_id,
            f"{DECOR_SUCCESS} تم التنصيب بنجاح! ✨\n\n"
            f"📌 لتفعيل التخزين أرسل من حسابك:\n"
            f"`.تخزين <لينك أو ID المجموعة>`",
            parse_mode='Markdown')
        clear_user_store(user_id)
        return ConversationHandler.END

    except Exception as e:
        logging.error(f"❌ خطأ في الإعداد النهائي: {e}")
        await send_clean(context, chat_id, f"{DECOR_ERROR} خطأ أثناء الإعداد: {str(e)}\n\nحاول مرة أخرى بإرسال /start")
        clear_user_store(user_id)
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_actions.pop(user_id, None)
    clear_user_store(user_id)

    await send_clean(context, user_id, f"{DECOR_CANCEL} تم الإلغاء")
    return ConversationHandler.END

# ==================== معالج الرسائل ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if user_id == ADMIN_ID and user_id in admin_actions:
        action = admin_actions[user_id]
        text = update.message.text.strip() if update.message.text else ""

        if action == "force_add":
            if not text:
                return
            ch = text.split()[-1].strip()
            if ch.startswith("https://t.me/"):
                ch = "@" + ch.split("/")[-1]
            if not ch.startswith("@"):
                ch = "@" + ch
            if ch not in config["FORCE_CHANNELS"]:
                config["FORCE_CHANNELS"].append(ch)
                save_config(config)
                await update.message.reply_text(f"{DECOR_CHECK} تم إضافة {ch}")
            else:
                await update.message.reply_text(f"{DECOR_SUBSCRIPTION} {ch} موجودة بالفعل")
            del admin_actions[user_id]
            return

        elif action == "force_remove":
            if not text:
                return
            ch = text.split()[-1].strip()
            if ch.startswith("https://t.me/"):
                ch = "@" + ch.split("/")[-1]
            if not ch.startswith("@"):
                ch = "@" + ch
            if ch in config["FORCE_CHANNELS"]:
                config["FORCE_CHANNELS"].remove(ch)
                save_config(config)
                await update.message.reply_text(f"{DECOR_CHECK} تم حذف {ch}")
            else:
                await update.message.reply_text(f"{DECOR_SUBSCRIPTION} {ch} غير موجودة")
            del admin_actions[user_id]
            return

        elif action == "set_group_photo":
            if update.message.photo:
                # صورة مباشرة - نحفظ file_id
                file_id = update.message.photo[-1].file_id
                # نحمل الصورة ونحفظها محلياً
                file = await update.message.photo[-1].get_file()
                file_path = os.path.join("data", f"group_photo_{int(datetime.now().timestamp())}.jpg")
                await file.download_to_drive(file_path)
                config["GROUP_PHOTO"] = file_path
                save_config(config)
                await update.message.reply_text(
                    f"{DECOR_CHECK} تم تحديث صورة المجموعة بنجاح! 🖼\n\n"
                    f"📌 هتتطبق على أي مجموعة جديدة بتتعمل"
                )
                del admin_actions[user_id]
                return
            elif text and (text.startswith("http://") or text.startswith("https://")):
                config["GROUP_PHOTO"] = text
                save_config(config)
                await update.message.reply_text(
                    f"{DECOR_CHECK} تم تحديث رابط صورة المجموعة! 🖼\n\n"
                    f"📌 هتتطبق على أي مجموعة جديدة بتتعمل"
                )
                del admin_actions[user_id]
                return
            else:
                await update.message.reply_text(
                    f"{DECOR_ERROR} أرسل صورة مباشرة أو رابط صورة يبدأ بـ https://"
                )
                return

        elif action == "force_setimg":
            if update.message.photo:
                file = await update.message.photo[-1].get_file()
                file_path = os.path.join("data", f"subs_image_{int(datetime.now().timestamp())}.jpg")
                await file.download_to_drive(file_path)
                config["SUBSCRIPTION_IMAGE"] = file_path
                save_config(config)
                await update.message.reply_text(f"{DECOR_CHECK} تم تحديث الصورة")
                del admin_actions[user_id]
                return
            elif text:
                config["SUBSCRIPTION_IMAGE"] = text
                save_config(config)
                await update.message.reply_text(f"{DECOR_CHECK} تم تحديث رابط الصورة")
                del admin_actions[user_id]
                return

        elif action == "set_max_sessions":
            if text.isdigit() and int(text) > 0:
                config["MAX_SESSIONS"] = int(text)
                save_config(config)
                await update.message.reply_text(f"{DECOR_CHECK} تم تغيير الحد الأقصى إلى: {text} جلسة")
            else:
                await update.message.reply_text(f"{DECOR_ERROR} أدخل رقم صحيح أكبر من 0")
            del admin_actions[user_id]
            return

    if user_id == ADMIN_ID and context.user_data.get("mode") == "broadcast":
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            users = []

        count = 0
        for u in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(chat_id=u, photo=update.message.photo[-1].file_id,
                                                  caption=update.message.caption or "")
                elif update.message.video:
                    await context.bot.send_video(chat_id=u, video=update.message.video.file_id,
                                                  caption=update.message.caption or "")
                elif update.message.document:
                    await context.bot.send_document(chat_id=u, document=update.message.document.file_id,
                                                     caption=update.message.caption or "")
                elif update.message.text:
                    await context.bot.send_message(chat_id=u, text=update.message.text)
                else:
                    continue
                count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.warning(f"⚠️ فشل الإذاعة للمستخدم {u}: {e}")

        await update.message.reply_text(f"{DECOR_BROADCAST} تم الإذاعة لـ {count} مستخدم")
        context.user_data["mode"] = None
        return

    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await send_disabled_message(context, user_id)
        return

    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return

    # ✅ message_handler مش بيبعت ترحيب خالص - الترحيب بس من /start
    return

# ==================== معالج أزرار الأدمن ====================
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id == ADMIN_ID:
        # ====== الرجوع للوحة الرئيسية ======
        if data == "admin_home":
            bot_enabled = config.get("BOT_ENABLED", True)
            max_sessions = config.get("MAX_SESSIONS", 50)
            current_sessions = len([f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
            bot_status = "مفعّل ✅" if bot_enabled else "معطل 🔴"
            caption = (f"{DECOR_TITLE.format('لوحة تحكم المطور')}\n\n"
                       f"حالة البوت: {bot_status}\n"
                       f"النشطة: {len(active_userbots)} | الجلسات: {current_sessions}/{max_sessions}")
            img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
            kb = admin_main_keyboard(bot_enabled, max_sessions, len(active_userbots))
            try:
                await query.message.edit_caption(caption=caption, reply_markup=kb)
            except Exception:
                try:
                    await query.message.edit_text(caption, reply_markup=kb)
                except Exception:
                    pass
            return

        # ====== قسم الإحصائيات ======
        elif data == "sec_stats":
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    users = json.load(f)
            except Exception:
                users = []
            all_sessions = [f.replace('.session','') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            max_s = config.get("MAX_SESSIONS", 50)
            active = list(active_userbots.keys())
            stopped = [s for s in all_sessions if s not in active]
            lines = [
                f"📊 الإحصائيات",
                f"",
                f"👥 المستخدمين: {len(users)}",
                f"⎙ الجلسات: {len(all_sessions)}/{max_s}",
                f"🟢 النشطة: {len(active)}",
                f"🔴 المتوقفة: {len(stopped)}",
            ]
            if active:
                lines += ["", "🟢 النشطة:"] + [f"  {i}. +{p}" for i, p in enumerate(active, 1)]
            if stopped:
                lines += ["", "🔴 المتوقفة:"] + [f"  {i}. +{p}" for i, p in enumerate(stopped, 1)]
            keyboard = [[back_btn()]]
            await show_section(query, "\n".join(lines), keyboard)
            return

        # ====== قسم الإذاعة ======
        elif data == "sec_broadcast":
            keyboard = [[back_btn()]]
            await show_section(query, "📣 الإذاعة\n\nأرسل الرسالة اللي عايز تذيعها\n(نص، صورة، فيديو، ملف):", keyboard)
            context.user_data["mode"] = "broadcast"
            return

        # ====== قسم الجلسات ======
        elif data == "sec_sessions":
            all_sessions = [f.replace('.session','') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            max_s = config.get("MAX_SESSIONS", 50)
            keyboard = [
                [
                    InlineKeyboardButton("➕ إنشاء جلسة", callback_data="create_session"),
                    InlineKeyboardButton("🗑 حذف جلسة",   callback_data="delete_session"),
                ],
                [
                    InlineKeyboardButton(f"⚙️ الحد الأقصى: {max_s}", callback_data="set_max_sessions"),
                ],
                [back_btn()],
            ]
            active = list(active_userbots.keys())
            stopped = [s for s in all_sessions if s not in active]
            lines = [
                f"⎙ الجلسات ({len(all_sessions)}/{max_s})",
                f"",
                f"🟢 نشطة: {len(active)}",
                f"🔴 متوقفة: {len(stopped)}",
            ]
            if all_sessions:
                lines.append("")
                for i, phone in enumerate(all_sessions, 1):
                    icon = "🟢" if phone in active_userbots else "🔴"
                    lines.append(f"{icon} {i}. +{phone}")
            await show_section(query, "\n".join(lines), keyboard)
            return

        # ====== قسم الاشتراك ======
        elif data == "sec_sub":
            channels = config.get("FORCE_CHANNELS", [])
            ch_text = "\n".join([f"  • {ch}" for ch in channels]) if channels else "  لا توجد قنوات"
            keyboard = [
                [
                    InlineKeyboardButton("➕ إضافة قناة",  callback_data="force_add"),
                    InlineKeyboardButton("➖ حذف قناة",    callback_data="force_remove"),
                ],
                [
                    InlineKeyboardButton("📋 القائمة",     callback_data="force_list"),
                    InlineKeyboardButton("🖼 صورة الاشتراك", callback_data="force_setimg"),
                ],
                [back_btn()],
            ]
            await show_section(query, f"🔒 إدارة الاشتراك الإجباري\n\nالقنوات الحالية:\n{ch_text}", keyboard)
            return

        # ====== قسم صورة المجموعة ======
        elif data == "sec_groupphoto":
            current_photo = config.get("GROUP_PHOTO", DEFAULT_GROUP_PHOTO_URL)
            is_url = current_photo.startswith("http")
            current_text = f"🔗 رابط" if is_url else f"📁 ملف محفوظ"
            keyboard = [
                [InlineKeyboardButton("🖼 تغيير الصورة", callback_data="set_group_photo")],
                [InlineKeyboardButton("👁 معاينة الصورة الحالية", callback_data="preview_group_photo")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")],
            ]
            await show_section(query,
                f"🖼 صورة المجموعة\n\n"
                f"الصورة الحالية: {current_text}\n\n"
                f"📌 الصورة دي هتتحط تلقائياً في كل مجموعة جديدة بتتعمل",
                keyboard)
            return

        elif data == "set_group_photo":
            admin_actions[user_id] = "set_group_photo"
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_groupphoto")]]
            await show_section(query,
                "🖼 أرسل الصورة الجديدة للمجموعة:\n\n"
                "• صورة مباشرة 📸\n"
                "• أو رابط صورة 🔗",
                keyboard)
            return

        elif data == "preview_group_photo":
            current_photo = config.get("GROUP_PHOTO", DEFAULT_GROUP_PHOTO_URL)
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_groupphoto")]]
            try:
                await query.message.reply_photo(
                    photo=current_photo,
                    caption="👆 صورة المجموعة الحالية",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await query.answer()
            except Exception:
                await show_section(query, f"❌ مش قادر أعرض الصورة\n\nالرابط: {current_photo}", keyboard)
            return

        elif data == "set_max_sessions":
            admin_actions[user_id] = "set_max_sessions"
            current = config.get("MAX_SESSIONS", 50)
            keyboard = [[back_btn()]]
            await show_section(query, f"⚙️ الحد الأقصى الحالي: {current} جلسة\n\nأرسل العدد الجديد:", keyboard)
            return

        # ====== broadcast (قديم للتوافق) ======
        elif data == "broadcast":
            context.user_data["mode"] = "broadcast"
            await query.answer("أرسل الرسالة الآن", show_alert=True)
            return

        elif data == "toggle_bot":
            config["BOT_ENABLED"] = not config.get("BOT_ENABLED", True)
            save_config(config)
            bot_enabled = config["BOT_ENABLED"]
            max_sessions = config.get("MAX_SESSIONS", 50)
            current_sessions = len([f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
            bot_status = "مفعّل ✅" if bot_enabled else "معطل 🔴"
            new_caption = (f"{DECOR_TITLE.format('لوحة تحكم المطور')}\n\n"
                           f"حالة البوت: {bot_status}\n"
                           f"النشطة: {len(active_userbots)} | الجلسات: {current_sessions}/{max_sessions}")
            new_kb = admin_main_keyboard(bot_enabled, max_sessions, len(active_userbots))
            # ✅ نعدل الـ caption بتاع الصورة في مكانها
            try:
                await query.message.edit_caption(caption=new_caption, reply_markup=new_kb)
            except Exception:
                try:
                    await query.message.edit_text(new_caption, reply_markup=new_kb)
                except Exception:
                    pass
            status_msg = "مفعّل ✅" if bot_enabled else "معطل 🔴"
            await query.answer(f"حالة البوت: {status_msg}", show_alert=True)
            return

        elif data == "delete_session":
            sessions = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            if not sessions:
                await query.answer("لا توجد جلسات", show_alert=True)
                return
            # ✅ إضافة تأكيد قبل الحذف
            keyboard = []
            for s in sessions:
                phone = s.replace('.session', '')
                status = "🟢" if phone in active_userbots else "🔴"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {phone} - اضغط للحذف",
                    callback_data=f"confirm_del|{s}"
                )])
            await query.message.reply_text(
                "⚠️ اختر جلسة للحذف (ستطلب منك تأكيد):",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        elif data.startswith("confirm_del|"):
            # ✅ جديد: طلب تأكيد قبل الحذف
            session_file = data.split("|")[1]
            phone = session_file.replace('.session', '')
            keyboard = [[
                InlineKeyboardButton(f"✅ نعم، احذف {phone}", callback_data=f"del_sess|{session_file}"),
                InlineKeyboardButton("❌ إلغاء", callback_data="delete_session")
            ]]
            await query.message.reply_text(
                f"⚠️ متأكد إنك عايز تحذف جلسة:\n{phone}؟",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        elif data.startswith("del_sess|"):
            session_file = data.split("|")[1]
            phone = session_file.replace('.session', '')
            try:
                if phone in active_userbots:
                    active_userbots[phone]['task'].cancel()
                    if 'monitor_task' in active_userbots[phone]:
                        active_userbots[phone]['monitor_task'].cancel()
                    await active_userbots[phone]['client'].disconnect()
                    del active_userbots[phone]
                os.remove(os.path.join(SESSIONS_DIR, session_file))
                json_file = os.path.join(SESSIONS_DIR, f"{phone}.json")
                if os.path.exists(json_file):
                    os.remove(json_file)
                await query.answer(f"{DECOR_CHECK} تم الحذف", show_alert=True)
            except Exception:
                await query.answer(f"{DECOR_ERROR} فشل الحذف", show_alert=True)
            return

        elif data == "force_add":
            admin_actions[user_id] = "force_add"
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_sub")]]
            await show_section(query, "➕ أرسل معرف القناة:\nمثال: @channel أو https://t.me/channel", keyboard)
            return
        elif data == "force_remove":
            admin_actions[user_id] = "force_remove"
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_sub")]]
            await show_section(query, "➖ أرسل معرف القناة للحذف:", keyboard)
            return
        elif data == "force_list":
            channels = config.get("FORCE_CHANNELS", [])
            ch_text = "\n".join([f"{i}. {ch}" for i, ch in enumerate(channels, 1)]) if channels else "لا توجد قنوات"
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_sub")]]
            await show_section(query, f"📋 القنوات:\n\n{ch_text}", keyboard)
            return
        elif data == "force_setimg":
            admin_actions[user_id] = "force_setimg"
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="sec_sub")]]
            await show_section(query, "🖼 أرسل صورة أو رابط صورة:", keyboard)
            return
        elif data.startswith("allow|"):
            # ✅ موافقة - بس نحذف رسالة الإشعار
            await query.message.delete()
            return
        elif data.startswith("delete_session|"):
            # ✅ التعديل: رفض الجلسة = حذف كامل من السيرفر
            session_file = data.split("|", 1)[1]
            phone = os.path.basename(session_file).replace('.session', '')
            try:
                # وقف اليوزربوت لو شغال
                if phone in active_userbots:
                    active_userbots[phone]['task'].cancel()
                    if 'monitor_task' in active_userbots[phone]:
                        active_userbots[phone]['monitor_task'].cancel()
                    await active_userbots[phone]['client'].disconnect()
                    del active_userbots[phone]
                # حذف ملف الجلسة
                session_path = os.path.join(SESSIONS_DIR, f"{phone}.session")
                if os.path.exists(session_path):
                    os.remove(session_path)
                # حذف ملف البيانات
                json_file = os.path.join(SESSIONS_DIR, f"{phone}.json")
                if os.path.exists(json_file):
                    os.remove(json_file)
                # حذف أي ملفات تانية مرتبطة بالجلسة
                for ext in ['-journal', '.session-journal']:
                    extra = os.path.join(SESSIONS_DIR, f"{phone}{ext}")
                    if os.path.exists(extra):
                        os.remove(extra)
                logging.info(f"🗑️ تم رفض وحذف جلسة: {phone}")
                await query.answer(f"{DECOR_CHECK} تم رفض وحذف الجلسة بالكامل", show_alert=True)
                await query.message.delete()
            except Exception as e:
                logging.error(f"❌ فشل حذف الجلسة: {e}")
                await query.answer(f"{DECOR_ERROR} فشل الحذف", show_alert=True)
            return

    if data == "force_joincheck":
        if await check_force_sub(user_id, context.bot):
            await query.answer(f"{DECOR_CHECK} تم التحقق!", show_alert=True)
            await send_welcome_message(query, context)
        else:
            await query.answer(f"{DECOR_SUBSCRIPTION} يجب الاشتراك أولاً!", show_alert=True)

# ==================== البرنامج الرئيسي ====================
async def main():
    logging.info("🚀 بدء تشغيل البوت...")
    await restart_userbots()

    app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
            CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
        ],
        states={
            API_ID_STATE:     [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)
            ],
            API_HASH_STATE:   [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)
            ],
            PHONE_STATE:      [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
            CODE_STATE:       [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)
            ],
            PASSWORD_STATE:   [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)
            ],
            BOT_TOKEN_STATE:  [
                CommandHandler("start", start),
                CallbackQueryHandler(create_session_callback, pattern="^create_session$"),
                CallbackQueryHandler(start_now_callback, pattern="^start_now$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),   # ✅ /start يريسيت المحادثة في أي وقت
        ],
        allow_reentry=True,
        conversation_timeout=600,  # ✅ لو المستخدم وقف 10 دقايق يتريسيت تلقائي
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

    logging.info("✅ البوت جاهز للعمل!")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        stop_signal = asyncio.Event()
        try:
            await stop_signal.wait()
        except (KeyboardInterrupt, SystemExit):
            logging.info("🛑 إيقاف البوت...")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("✅ تم إيقاف البوت بنجاح")
    except Exception as e:
        logging.error(f"❌ خطأ فادح: {e}")
        raise
