import os
import re
import asyncio
import logging
import json
from datetime import datetime
from telethon import events, TelegramClient
from telethon.errors import (
    ChatAdminRequiredError, FloodWaitError,
    SessionPasswordNeededError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import (
    LeaveChannelRequest, EditPhotoRequest, CreateChannelRequest,
    InviteToChannelRequest, EditAdminRequest, GetParticipantRequest
)
from telethon.tl.types import (
    InputChatUploadedPhoto, ChannelParticipantsAdmins, ChatAdminRights
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors.rpcerrorlist import UserNotParticipantError, UserIdInvalidError
import aiohttp
from deep_translator import GoogleTranslator

# ═══════════════════════════════════════════
#              الإعدادات الأساسية
# ═══════════════════════════════════════════

logging.basicConfig(
    filename='telthon_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

OFFICIAL_CHANNEL_LINK = "https://t.me/FY_TF"

GLOBAL_BANNED_WORDS = {
    "كس","كسك","كسمك","كسم","طيز","طيزك","زب","زبي","زبك",
    "نيك","نيكني","نيكك","انيكك","متناك","متناكة","منيوك","منيوكة",
    "شرموط","شرموطة","شراميط","عرص","عرصة","معرص","قحبة","قحب",
    "وسخة","وسخ","خول","خولات","لبوة","بزاز","بز","احا","اح",
    "ابن المتناكة","ابن الشرموطة","ابن القحبة","ابن الوسخة",
    "بنت المتناكة","بنت الشرموطة","بنت القحبة","بنت الوسخة",
    "يلعن","يلعن ابوك","يلعن امك","يلعن دينك","كسمين",
    "منايك","منايكة","عرصات","لبؤة","فشخ","فشخك","مفشوخ","مفشوخة",
    "جلق","جلقلك","لوطي","خنيث","بيتش","سكس","sex","porn","xxx",
    "fuck","bitch","pussy","dick","cock","ass","shit",
}

# ═══════════════════════════════════════════
#           نص قائمة الأوامر
# ═══════════════════════════════════════════

COMMANDS_TEXT = """
╔══════════════════════════╗
       📌 قائمة الأوامر
╚══════════════════════════╝

┌─── 🔧 التحكم في البوت ───
│ .تفعيل_البوت
│ .تعطيل_البوت
│ .حالة_البوت
│ .ايقاف
└──────────────────────────

┌─── 📦 التخزين والـ Inbox ───
│ .تخزين <لينك أو ID>
│ .حالة_التخزين
└──────────────────────────

┌─── 👤 معلومات وعامة ───
│ .معلومات
│ .كشف  (رد على مستخدم)
│ .ترجم <نص>
│ .عدد_المحادثات
└──────────────────────────

┌─── 📢 الإذاعة ───
│ .اذاعة <رسالة>
│ .اذاعة_خاص <رسالة>
│ .اذاعة_جروب <رسالة>
│ .اذاعة_قناة <رسالة>
│ .اذاعة_صورة  (رد على صورة)
│ .سبام <عدد> <رسالة>
└──────────────────────────

┌─── 🗑️ الحذف ───
│ .حذف  (رد)
│ .حذفكل
│ .تنظيف_الخاص
└──────────────────────────

┌─── 🎉 الترحيب (خاص) ───
│ .ترحيب تشغيل / ايقاف / حالة
│ .ترحيب_نص <النص>
│ .ترحيب_صورة  (رد)
│ .ترحيب_بدون_صورة
└──────────────────────────

┌─── 🔄 الردود التلقائية ───
│ .فلتر <كلمة> <الرد>
│ .حذف_فلتر <كلمة>
│ .الفلاتر
│ .رد_عام <كلمة> <الرد>
│ .رد_عام_ملصق <كلمة>  (رد)
│ .حذف_رد_عام <كلمة>
└──────────────────────────

┌─── 👥 إدارة الأعضاء ───
│ .حظر  (رد / @يوزر / ID)
│ .فكحظر  (رد / @يوزر / ID)
│ .كتم  (رد / @يوزر / ID)
│ .فككتم  (رد / @يوزر / ID)
│ .كتم_مشرف  (رد)
│ .فك_كتم_مشرف  (رد)
│ .طرد  (رد / @يوزر / ID)
│ .اضافة @يوزر
│ .تصفية
└──────────────────────────

┌─── 🔑 الملكية ───
│ .نقل_ملكية <ID أو @يوزر>
└──────────────────────────

┌─── 🔒 الحماية ───
│ .منع <كلمة>
│ .حذف_منع <كلمة>
│ .قائمة_المنع
│ .قفل_روابط / .فتح_روابط
│ .قفل <صور/فيديو/ملصقات/ملفات/صوت/gif>
│ .فتح <نوع الميديا>
│ .قائمة_القفل
│ .منع_تصفية <عدد>
│ .الغاء_منع_تصفية
└──────────────────────────

┌─── ⚙️ إعدادات الجروب ───
│ .وصف <نص>
│ .صورةمجموعة  (رد على صورة)
│ .المشرفين
│ .رابط_الدعوة
│ .منشن_الكل
│ .فحص_الاعضاء
│ .تصدير_الاعضاء
│ .حالة_الجروب
│ .انشاءمجموعات
└──────────────────────────

┌─── 🖼 الملف الشخصي ───
│ .صورتي  (رد على صورة)
│ .اسمي <الاسم>
│ .صوت <رابط>
│ .ارسال_ملف <رابط>
└──────────────────────────
"""

# ═══════════════════════════════════════════
#              دالة اليوزربوت الرئيسية
# ═══════════════════════════════════════════

async def start_userbot(client: TelegramClient, target_chat, user_data_store):
    print(f"✅ تيلثون شغال على: {user_data_store['phone']}")

    try:
        if not client.is_connected():
            await client.connect()
        me = await client.get_me()
        if not me:
            print("❌ فشل get_me - الجلسة غير صالحة")
            return
    except Exception as e:
        print(f"❌ فشل بدء اليوزربوت: {e}")
        return

    owner_id = me.id
    print(f"✅ {me.first_name} | ID: {owner_id}")

    # ═══ المتغيرات الداخلية ═══
    bot_enabled        = True
    keep_alive         = True
    welcome_enabled    = True
    welcome_image_path = None
    welcome_sent       = set()
    target_chat_entity = None

    filters_dict          = {}
    custom_banned_words   = {}
    locked_media          = {}
    global_replies        = {}
    global_replies_stickers = {}
    muted_admins          = {}
    muted_users           = {}
    links_locked          = set()

    # منع التصفية: {chat_id: threshold}
    anti_purge_enabled  = {}
    # عداد الطرد/الحظر لكل مشرف: {chat_id: {admin_id: count}}
    admin_action_count  = {}

    welcome_text_template = (
        "اهلاً وسهلاً بيك 🔥\n"
        "سيب رسالتك هنا وهنرد عليك في أقرب وقت 💬\n"
        f"[القناة الرسمية]({OFFICIAL_CHANNEL_LINK})"
    )

    # ════════════════════════════════════════
    #           الدوال المساعدة
    # ════════════════════════════════════════

    async def is_admin(chat_id, user_id):
        try:
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            return any(a.id == user_id for a in admins)
        except:
            return False

    async def get_user_from_input(user_input, chat_id=None):
        try:
            user_input = str(user_input).strip('@')
            if user_input.isdigit():
                uid = int(user_input)
                entity = None
                if chat_id:
                    try:
                        parts = await client.get_participants(chat_id, limit=1000)
                        for p in parts:
                            if p.id == uid:
                                entity = p
                                break
                    except:
                        pass
                return uid, entity
            else:
                entity = await client.get_entity(user_input)
                return entity.id, entity
        except:
            return None, None

    def contains_banned_word(text, chat_id):
        t = text.lower()
        if any(w in t for w in GLOBAL_BANNED_WORDS):
            return True
        return any(w in t for w in custom_banned_words.get(chat_id, []))

    def contains_link(text):
        return bool(re.search(r'(https?://|www\.|t\.me/|telegram\.me/|@)', text, re.IGNORECASE))

    async def reply_or_edit(event, text, **kwargs):
        try:
            if event.out:
                await event.edit(text, **kwargs)
            else:
                await event.respond(text, **kwargs)
        except:
            try:
                await event.respond(text, **kwargs)
            except Exception as e:
                logging.error(f"reply_or_edit error: {e}")

    def fmt(title, lines):
        """ينسق الرسالة بإطار موحد"""
        body = "\n".join(f"│ {l}" for l in lines)
        return f"┌─── {title}\n{body}\n└" + "─" * (len(title) + 4)

    # ════════════════════════════════════════
    #              نظام الـ INBOX
    # ════════════════════════════════════════

    async def build_inbox_caption(sender, chat, text, source_type):
        fname = getattr(sender, 'first_name', '') or ''
        lname = getattr(sender, 'last_name', '') or ''
        name  = f"{fname} {lname}".strip() or "مجهول"
        uname = getattr(sender, 'username', None)
        sid   = getattr(sender, 'id', None)
        cname = getattr(chat, 'title', '') if chat and hasattr(chat, 'title') else ''

        icons = {"private": "💬 رسالة خاصة", "mention": "📢 منشن", "reply": "↩️ رد على رسالتك"}
        label = icons.get(source_type, "📩 رسالة")

        lines = [f"┌ {label}"]
        lines.append(f"├ 👤 من: **{name}**")
        if uname: lines.append(f"├ 🔗 @{uname}")
        if sid:   lines.append(f"├ 🆔 `{sid}`")
        if cname: lines.append(f"├ 🏠 {cname}")
        if text and text.strip():
            preview = text[:200] + ("..." if len(text) > 200 else "")
            lines.append(f"├ 📝 {preview}")
        lines.append(f"└ 🕐 {datetime.now().strftime('%H:%M - %d/%m/%Y')}")
        return "\n".join(lines)

    async def get_inbox_markup(sender):
        from telethon.tl.types import KeyboardButtonUrl, ReplyInlineMarkup, KeyboardButtonRow
        sid   = getattr(sender, 'id', None)
        uname = getattr(sender, 'username', None)
        fname = getattr(sender, 'first_name', '') or 'المستخدم'
        if not sid:
            return None
        url = f"https://t.me/{uname}" if uname else f"tg://user?id={sid}"
        btn = KeyboardButtonUrl(text=f"💬 فتح محادثة مع {fname}", url=url)
        return ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[btn])])

    async def forward_to_inbox(event, source_type):
        if not target_chat_entity:
            return
        try:
            sender  = await event.get_sender()
            chat    = await event.get_chat()
            caption = await build_inbox_caption(sender, chat, event.raw_text or "", source_type)
            markup  = await get_inbox_markup(sender)
            if event.media:
                await client.send_file(target_chat_entity, event.media,
                                       caption=caption, reply_markup=markup, parse_mode='markdown')
            else:
                await client.send_message(target_chat_entity, caption,
                                          reply_markup=markup, parse_mode='markdown')
        except Exception as e:
            logging.error(f"forward_to_inbox error: {e}")

    # ════════════════════════════════════════
    #          نظام منع التصفية
    # ════════════════════════════════════════

    async def check_anti_purge(event, action_type):
        """
        يراقب طرد/حظر المشرفين.
        لو مشرف تجاوز الـ threshold → ينزل من الإشراف فوراً
        """
        chat_id = event.chat_id
        if chat_id not in anti_purge_enabled:
            return

        threshold = anti_purge_enabled[chat_id]
        acting_admin_id = event.sender_id
        if not acting_admin_id or acting_admin_id == owner_id:
            return

        # تأكد إنه فعلاً مشرف
        if not await is_admin(chat_id, acting_admin_id):
            return

        # زود العداد
        if chat_id not in admin_action_count:
            admin_action_count[chat_id] = {}
        if acting_admin_id not in admin_action_count[chat_id]:
            admin_action_count[chat_id][acting_admin_id] = 0

        admin_action_count[chat_id][acting_admin_id] += 1
        count = admin_action_count[chat_id][acting_admin_id]

        if count >= threshold:
            # صفّر العداد
            admin_action_count[chat_id][acting_admin_id] = 0
            try:
                # نزّله من الإشراف
                await client(EditAdminRequest(
                    channel=chat_id,
                    user_id=acting_admin_id,
                    admin_rights=ChatAdminRights(
                        change_info=False, post_messages=False, edit_messages=False,
                        delete_messages=False, ban_users=False, invite_users=False,
                        pin_messages=False, add_admins=False, anonymous=False,
                        manage_call=False, other=False
                    ),
                    rank=""
                ))
                # اجلب اسمه
                try:
                    admin_entity = await client.get_entity(acting_admin_id)
                    admin_name = admin_entity.first_name or str(acting_admin_id)
                except:
                    admin_name = str(acting_admin_id)

                await client.send_message(
                    chat_id,
                    f"⚠️ **تحذير: محاولة تصفية المجموعة**\n\n"
                    f"👤 المشرف: **{admin_name}** (`{acting_admin_id}`)\n"
                    f"📊 عدد الإجراءات: {count}\n"
                    f"🚫 تم تنزيله من الإشراف فوراً\n"
                    f"🕐 {datetime.now().strftime('%H:%M - %d/%m/%Y')}",
                    parse_mode='markdown'
                )
            except Exception as e:
                logging.error(f"anti_purge error: {e}")

    # ════════════════════════════════════════
    #        نقل الملكية (دالة منفصلة)
    # ════════════════════════════════════════

    async def transfer_ownership(chat_id, new_owner_id, event):
        try:
            try:
                new_owner = await client.get_entity(new_owner_id)
            except (UserIdInvalidError, ValueError):
                await reply_or_edit(event, "❌ المستخدم غير موجود!")
                return
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
                return

            # تحقق من العضوية
            is_member = False
            try:
                await client(GetParticipantRequest(chat_id, new_owner_id))
                is_member = True
            except UserNotParticipantError:
                pass
            except:
                pass

            if not is_member:
                try:
                    await client(InviteToChannelRequest(chat_id, [new_owner]))
                    await asyncio.sleep(2)
                except Exception as e:
                    await reply_or_edit(event, f"❌ فشل إضافة المستخدم: {e}")
                    return

            await reply_or_edit(event,
                f"🔐 **نقل الملكية إلى:** {new_owner.first_name}\n\n"
                f"⚠️ لا يمكن التراجع عن هذا الإجراء!\n"
                f"📲 أرسل كلمة سر 2FA للتأكيد\n"
                f"أو `.الغاء` للإلغاء"
            )

            try:
                response = await client.wait_for(
                    events.NewMessage(from_users=owner_id, chats=event.chat_id),
                    timeout=120
                )
            except asyncio.TimeoutError:
                await event.respond("⏰ انتهت المهلة! تم الإلغاء")
                return

            pwd_text = response.raw_text.strip()
            try: await response.delete()
            except: pass

            if pwd_text == ".الغاء":
                await event.respond("🛑 تم إلغاء نقل الملكية")
                return

            try:
                from telethon.tl.functions.account import GetPasswordRequest, CheckPasswordRequest
                from telethon.password import compute_check
                from telethon.tl.functions.channels import EditCreatorRequest

                pwd = await client(GetPasswordRequest())
                pwd_check = compute_check(pwd, pwd_text)
                await client(CheckPasswordRequest(password=pwd_check))

                full_rights = ChatAdminRights(
                    change_info=True, post_messages=True, edit_messages=True,
                    delete_messages=True, ban_users=True, invite_users=True,
                    pin_messages=True, add_admins=True, anonymous=False,
                    manage_call=True, other=True, manage_topics=True
                )
                await client(EditAdminRequest(channel=chat_id, user_id=new_owner_id,
                                              admin_rights=full_rights, rank="مالك"))
                pwd2 = await client(GetPasswordRequest())
                check2 = compute_check(pwd2, pwd_text)
                await client(EditCreatorRequest(channel=chat_id, user_id=new_owner_id, password=check2))
                await event.respond(
                    f"✅ **تم نقل الملكية بنجاح!**\n\n"
                    f"👤 المالك الجديد: {new_owner.first_name}\n"
                    f"🆔 `{new_owner.id}`"
                )
            except Exception as e:
                await event.respond(f"❌ خطأ في النقل: {e}")
        except Exception as e:
            await event.respond(f"❌ خطأ عام: {e}")

    # ════════════════════════════════════════
    #           الـ Event Handler الرئيسي
    # ════════════════════════════════════════

    @client.on(events.NewMessage)
    async def handle_all(event):
        nonlocal welcome_enabled, welcome_image_path, welcome_text_template
        nonlocal bot_enabled, keep_alive, target_chat_entity

        text      = event.raw_text or ""
        chat_id   = event.chat_id
        sender_id = event.sender_id

        # ══════════════════════════════════════
        #   INBOX - رسائل واردة (مش منك)
        # ══════════════════════════════════════
        if not event.out:
            try:
                sender = await event.get_sender()
                is_bot = sender and getattr(sender, 'bot', False)
                if not is_bot and sender_id != owner_id:
                    if event.is_private:
                        await forward_to_inbox(event, "private")
                    elif event.is_group or event.is_channel:
                        if event.mentioned:
                            await forward_to_inbox(event, "mention")
                        elif event.is_reply:
                            try:
                                replied = await event.get_reply_message()
                                if replied and replied.sender_id == owner_id:
                                    await forward_to_inbox(event, "reply")
                            except:
                                pass
            except Exception as e:
                logging.error(f"inbox error: {e}")

        # ══════════════════════════════════════
        #  أوامر التحكم - منك أنت فقط (event.out)
        # ══════════════════════════════════════
        if not event.out:
            # حماية الجروبات
            if event.is_group and bot_enabled:
                s_admin = await is_admin(chat_id, sender_id)

                if chat_id in muted_admins and sender_id in muted_admins[chat_id]:
                    try: await event.delete()
                    except: pass
                    return

                if chat_id in muted_users and sender_id in muted_users[chat_id]:
                    try: await event.delete()
                    except: pass
                    return

                if not s_admin:
                    if contains_banned_word(text, chat_id):
                        try: await event.delete()
                        except: pass
                        return
                    if chat_id in links_locked and contains_link(text):
                        try: await event.delete()
                        except: pass
                        return
                    if chat_id in locked_media:
                        locks = locked_media[chat_id]
                        should_del = (
                            ('صور' in locks and event.photo) or
                            ('فيديو' in locks and event.video) or
                            ('ملصقات' in locks and event.sticker) or
                            ('ملفات' in locks and event.document and not event.sticker and not event.video and not event.audio) or
                            ('صوت' in locks and (event.audio or event.voice)) or
                            ('gif' in locks and event.gif)
                        )
                        if should_del:
                            try: await event.delete()
                            except: pass
                            return

            # ردود تلقائية
            if text in filters_dict:
                await event.respond(filters_dict[text])
            if text.lower() in global_replies:
                await event.respond(global_replies[text.lower()])
            elif text.lower() in global_replies_stickers:
                await client.send_file(chat_id, global_replies_stickers[text.lower()], reply_to=event.id)

            # ترحيب في الخاص
            if event.is_private and welcome_enabled:
                sender = await event.get_sender()
                if sender and not sender.bot and sender_id not in welcome_sent:
                    welcome_sent.add(sender_id)
                    wtext = welcome_text_template
                    try:
                        if welcome_image_path and os.path.exists(welcome_image_path):
                            await client.send_file(chat_id, welcome_image_path,
                                                   caption=wtext, parse_mode='markdown')
                        else:
                            await event.respond(wtext, parse_mode='markdown')
                    except:
                        try: await event.respond(wtext, parse_mode='markdown')
                        except: pass
            return  # كل اللي فوق للرسائل الواردة فقط

        # ══════════════════════════════════════
        #  من هنا: أوامر صاحب الحساب فقط
        # ══════════════════════════════════════
        if not text.startswith('.'):
            return

        # أوامر التحكم تشتغل حتى لو البوت معطل
        if text == ".تفعيل_البوت":
            bot_enabled = True
            await reply_or_edit(event, fmt("🔧 التحكم في البوت", ["✅ تم تفعيل البوت", "🟢 جميع الميزات تعمل الآن"]))
            return

        if text == ".تعطيل_البوت":
            bot_enabled = False
            await reply_or_edit(event, fmt("🔧 التحكم في البوت", ["⏸️ تم تعطيل البوت", "🔴 الميزات متوقفة", "💡 .تفعيل_البوت للإعادة"]))
            return

        if text == ".حالة_البوت":
            status = "🟢 مفعّل" if bot_enabled else "🔴 معطّل"
            storage = f"✅ {target_chat_entity.title}" if target_chat_entity else "❌ غير مربوط"
            await reply_or_edit(event, fmt("🔧 حالة البوت", [
                f"⚡ الحالة: {status}",
                f"👤 الحساب: {me.first_name}",
                f"📦 التخزين: {storage}",
                f"🕐 {datetime.now().strftime('%H:%M - %d/%m/%Y')}"
            ]))
            return

        if text == ".ايقاف":
            await reply_or_edit(event, fmt("🔧 التحكم في البوت", ["🛑 جاري الإيقاف..."]))
            await asyncio.sleep(1)
            keep_alive = False
            await client.disconnect()
            return

        if text == ".الاوامر":
            await reply_or_edit(event, COMMANDS_TEXT)
            return

        # باقي الأوامر تشتغل بس لو البوت مفعّل
        if not bot_enabled:
            return

        # ══════════════════════════════════════
        #    📦 أوامر التخزين والـ Inbox
        # ══════════════════════════════════════

        if text.startswith(".تخزين"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                storage = f"✅ {target_chat_entity.title}" if target_chat_entity else "❌ غير مربوط"
                await reply_or_edit(event, fmt("📦 التخزين", [
                    "الاستخدام: .تخزين <لينك أو ID>",
                    "",
                    f"الحالة: {storage}"
                ]))
                return
            try:
                await reply_or_edit(event, fmt("📦 التخزين", ["⏳ جاري الربط..."]))
                entity = await client.get_entity(parts[1].strip())
                target_chat_entity = entity
                await reply_or_edit(event, fmt("📦 التخزين", [
                    f"✅ تم الربط بنجاح!",
                    f"📦 المجموعة: {entity.title}",
                    f"🆔 ID: {entity.id}",
                    "",
                    "الآن الرسائل هتتخزن تلقائياً 📥"
                ]))
            except Exception as e:
                await reply_or_edit(event, fmt("📦 التخزين", [
                    "❌ فشل الربط!",
                    "تأكد إنك عضو في المجموعة",
                    f"الخطأ: {str(e)}"
                ]))
            return

        if text == ".حالة_التخزين":
            if target_chat_entity:
                await reply_or_edit(event, fmt("📦 حالة التخزين", [
                    f"✅ مربوط بـ: {target_chat_entity.title}",
                    f"🆔 ID: {target_chat_entity.id}"
                ]))
            else:
                await reply_or_edit(event, fmt("📦 حالة التخزين", [
                    "❌ غير مربوط",
                    "استخدم: .تخزين <لينك أو ID>"
                ]))
            return

        # ══════════════════════════════════════
        #    👤 أوامر المعلومات والعامة
        # ══════════════════════════════════════

        if text == ".معلومات":
            await reply_or_edit(event, fmt("👤 معلومات الحساب", [
                f"الاسم: {me.first_name} {me.last_name or ''}",
                f"🆔 ID: `{me.id}`",
                f"📱 يوزر: @{me.username or 'لا يوجد'}",
                f"🤖 بوت: {'نعم' if me.bot else 'لا'}"
            ]))
            return

        if text == ".كشف" and event.is_reply:
            reply = await event.get_reply_message()
            sender = await reply.get_sender()
            if sender:
                await reply_or_edit(event, fmt("👤 معلومات المستخدم", [
                    f"الاسم: {sender.first_name} {getattr(sender,'last_name','') or ''}",
                    f"🆔 ID: `{sender.id}`",
                    f"📱 يوزر: @{sender.username or 'لا يوجد'}",
                    f"🤖 بوت: {'نعم' if sender.bot else 'لا'}",
                    f"🔇 محظور: {'نعم' if getattr(sender,'restricted',False) else 'لا'}"
                ]))
            return

        if text.startswith(".ترجم "):
            to_translate = text[7:].strip()
            try:
                translated = GoogleTranslator(source='auto', target='ar').translate(to_translate)
                if translated == to_translate:
                    translated = GoogleTranslator(source='auto', target='en').translate(to_translate)
                await reply_or_edit(event, fmt("🌐 الترجمة", [
                    f"الأصل: {to_translate}",
                    f"الترجمة: {translated}"
                ]))
            except Exception as e:
                await reply_or_edit(event, fmt("🌐 الترجمة", [f"❌ فشل الترجمة: {e}"]))
            return

        if text == ".عدد_المحادثات":
            privates = groups = channels = 0
            async for d in client.iter_dialogs():
                if d.is_user: privates += 1
                elif d.is_group: groups += 1
                elif d.is_channel: channels += 1
            await reply_or_edit(event, fmt("📊 إحصائيات المحادثات", [
                f"💬 خاص: {privates}",
                f"👥 جروبات: {groups}",
                f"📢 قنوات: {channels}",
                f"📊 الإجمالي: {privates+groups+channels}"
            ]))
            return

        # ══════════════════════════════════════
        #    📢 أوامر الإذاعة
        # ══════════════════════════════════════

        if text.startswith(".اذاعة ") or text.startswith(".اذاعة_خاص ") or \
           text.startswith(".اذاعة_جروب ") or text.startswith(".اذاعة_قناة "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return
            msg      = parts[1]
            cmd      = parts[0]
            sent = failed = 0
            await reply_or_edit(event, fmt("📢 الإذاعة", ["⏳ جاري الإرسال..."]))
            async for d in client.iter_dialogs():
                try:
                    if cmd == ".اذاعة" or \
                       (cmd == ".اذاعة_خاص" and d.is_user) or \
                       (cmd == ".اذاعة_جروب" and d.is_group) or \
                       (cmd == ".اذاعة_قناة" and d.is_channel):
                        await client.send_message(d.id, msg)
                        sent += 1
                        await asyncio.sleep(1)
                except:
                    failed += 1
            await reply_or_edit(event, fmt("📢 الإذاعة", [
                f"✅ أُرسلت: {sent}",
                f"❌ فشلت: {failed}"
            ]))
            return

        if text == ".اذاعة_صورة" and event.is_reply:
            reply = await event.get_reply_message()
            if not reply.photo:
                await reply_or_edit(event, fmt("📢 الإذاعة", ["❌ رد على صورة!"]))
                return
            sent = failed = 0
            await reply_or_edit(event, fmt("📢 الإذاعة", ["⏳ جاري إرسال الصورة..."]))
            async for d in client.iter_dialogs():
                try:
                    await client.send_file(d.id, reply.photo, caption=reply.text or "")
                    sent += 1
                    await asyncio.sleep(1)
                except:
                    failed += 1
            await reply_or_edit(event, fmt("📢 الإذاعة", [f"✅ {sent}", f"❌ {failed}"]))
            return

        if text.startswith(".سبام "):
            args = text.split(maxsplit=2)
            if len(args) < 3 or not args[1].isdigit():
                await reply_or_edit(event, fmt("📢 سبام", ["الاستخدام: .سبام <عدد> <رسالة>"]))
                return
            count = min(int(args[1]), 50)
            msg   = args[2]
            for i in range(count):
                try:
                    await client.send_message(chat_id, msg)
                    await asyncio.sleep(0.5)
                except:
                    break
            return

        # ══════════════════════════════════════
        #    🗑️ أوامر الحذف
        # ══════════════════════════════════════

        if text == ".حذف" and event.is_reply:
            try:
                reply = await event.get_reply_message()
                await reply.delete()
                await event.delete()
            except Exception as e:
                await reply_or_edit(event, fmt("🗑️ الحذف", [f"❌ {e}"]))
            return

        if text == ".حذفكل":
            deleted = 0
            async for msg in client.iter_messages(chat_id, from_user='me', limit=100):
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.1)
                except:
                    pass
            await client.send_message(chat_id, fmt("🗑️ الحذف", [f"✅ تم حذف {deleted} رسالة"]))
            return

        if text == ".تنظيف_الخاص" and event.is_private:
            deleted = 0
            async for msg in client.iter_messages(chat_id, limit=200):
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
            return

        # ══════════════════════════════════════
        #    🎉 أوامر الترحيب
        # ══════════════════════════════════════

        if text == ".ترحيب تشغيل":
            welcome_enabled = True
            await reply_or_edit(event, fmt("🎉 الترحيب", ["✅ تم تفعيل الترحيب التلقائي"]))
            return

        if text == ".ترحيب ايقاف":
            welcome_enabled = False
            await reply_or_edit(event, fmt("🎉 الترحيب", ["⏸️ تم إيقاف الترحيب التلقائي"]))
            return

        if text == ".ترحيب حالة":
            status = "✅ مفعّل" if welcome_enabled else "❌ موقوف"
            has_img = "✅ موجودة" if welcome_image_path else "❌ لا توجد"
            await reply_or_edit(event, fmt("🎉 الترحيب", [
                f"الحالة: {status}",
                f"الصورة: {has_img}"
            ]))
            return

        if text.startswith(".ترحيب_نص "):
            welcome_text_template = text[11:]
            await reply_or_edit(event, fmt("🎉 الترحيب", ["✅ تم تغيير نص الترحيب"]))
            return

        if text == ".ترحيب_صورة" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.photo:
                path = f"welcome_{me.id}.jpg"
                await client.download_media(reply.photo, path)
                welcome_image_path = path
                await reply_or_edit(event, fmt("🎉 الترحيب", ["✅ تم تعيين صورة الترحيب"]))
            else:
                await reply_or_edit(event, fmt("🎉 الترحيب", ["❌ رد على صورة!"]))
            return

        if text == ".ترحيب_بدون_صورة":
            welcome_image_path = None
            await reply_or_edit(event, fmt("🎉 الترحيب", ["✅ تم إزالة الصورة"]))
            return

        # ══════════════════════════════════════
        #    🔄 الردود التلقائية
        # ══════════════════════════════════════

        if text.startswith(".فلتر "):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                filters_dict[parts[1]] = parts[2]
                await reply_or_edit(event, fmt("🔄 الفلاتر", [f"✅ تم إضافة: {parts[1]}"]))
            return

        if text.startswith(".حذف_فلتر "):
            key = text.split(maxsplit=1)[1]
            if key in filters_dict:
                del filters_dict[key]
                await reply_or_edit(event, fmt("🔄 الفلاتر", [f"✅ تم حذف: {key}"]))
            else:
                await reply_or_edit(event, fmt("🔄 الفلاتر", [f"❌ {key} غير موجود"]))
            return

        if text == ".الفلاتر":
            if filters_dict:
                items = [f"• {k} → {v}" for k, v in filters_dict.items()]
            else:
                items = ["لا توجد فلاتر"]
            await reply_or_edit(event, fmt("🔄 الفلاتر", items))
            return

        if text.startswith(".رد_عام "):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                global_replies[parts[1].lower()] = parts[2]
                await reply_or_edit(event, fmt("🔄 الردود التلقائية", [f"✅ تم إضافة رد: {parts[1]}"]))
            return

        if text == ".رد_عام_ملصق" and event.is_reply:
            parts = text.split(maxsplit=1)
            reply = await event.get_reply_message()
            if len(parts) > 1 and reply.sticker:
                global_replies_stickers[parts[1].lower()] = reply.sticker
                await reply_or_edit(event, fmt("🔄 الردود التلقائية", [f"✅ تم إضافة رد بملصق: {parts[1]}"]))
            return

        if text.startswith(".حذف_رد_عام "):
            key = text.split(maxsplit=1)[1].lower()
            removed = False
            if key in global_replies:
                del global_replies[key]
                removed = True
            if key in global_replies_stickers:
                del global_replies_stickers[key]
                removed = True
            msg = f"✅ تم حذف: {key}" if removed else f"❌ {key} غير موجود"
            await reply_or_edit(event, fmt("🔄 الردود التلقائية", [msg]))
            return

        # ══════════════════════════════════════
        #    👥 أوامر إدارة الأعضاء
        # ══════════════════════════════════════

        if text.startswith(".حظر"):
            target_id = target_entity = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = reply.sender_id
            else:
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    target_id, target_entity = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("👥 الحظر", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, target_id, view_messages=False)
                name = getattr(target_entity, 'first_name', str(target_id)) if target_entity else str(target_id)
                await reply_or_edit(event, fmt("👥 الحظر", [f"✅ تم حظر: {name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 الحظر", [f"❌ {e}"]))
            return

        if text.startswith(".فكحظر"):
            target_id = target_entity = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = reply.sender_id
            else:
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    target_id, target_entity = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("👥 فك الحظر", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, target_id, view_messages=True)
                name = getattr(target_entity, 'first_name', str(target_id)) if target_entity else str(target_id)
                await reply_or_edit(event, fmt("👥 فك الحظر", [f"✅ تم فك حظر: {name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 فك الحظر", [f"❌ {e}"]))
            return

        if text.startswith(".كتم"):
            target_id = target_entity = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = reply.sender_id
            else:
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    target_id, target_entity = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("👥 الكتم", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, target_id,
                    send_messages=False, send_media=False, send_stickers=False,
                    send_gifs=False, send_games=False, send_inline=False)
                muted_users.setdefault(chat_id, set()).add(target_id)
                name = getattr(target_entity, 'first_name', str(target_id)) if target_entity else str(target_id)
                # حذف رسائله
                async for msg in client.iter_messages(chat_id, from_user=target_id, limit=50):
                    try: await msg.delete()
                    except: pass
                await reply_or_edit(event, fmt("👥 الكتم", [f"✅ تم كتم: {name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 الكتم", [f"❌ {e}"]))
            return

        if text.startswith(".فككتم"):
            target_id = target_entity = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = reply.sender_id
            else:
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    target_id, target_entity = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("👥 فك الكتم", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, target_id,
                    send_messages=True, send_media=True, send_stickers=True,
                    send_gifs=True, send_games=True, send_inline=True)
                if chat_id in muted_users:
                    muted_users[chat_id].discard(target_id)
                name = getattr(target_entity, 'first_name', str(target_id)) if target_entity else str(target_id)
                await reply_or_edit(event, fmt("👥 فك الكتم", [f"✅ تم فك كتم: {name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 فك الكتم", [f"❌ {e}"]))
            return

        if text == ".كتم_مشرف" and event.is_reply:
            reply = await event.get_reply_message()
            target_id = reply.sender_id
            muted_admins.setdefault(chat_id, set()).add(target_id)
            # احذف رسائله
            async for msg in client.iter_messages(chat_id, from_user=target_id, limit=50):
                try: await msg.delete()
                except: pass
            await reply_or_edit(event, fmt("👥 كتم مشرف", [f"✅ تم كتم المشرف `{target_id}`"]))
            return

        if text == ".فك_كتم_مشرف" and event.is_reply:
            reply = await event.get_reply_message()
            target_id = reply.sender_id
            if chat_id in muted_admins:
                muted_admins[chat_id].discard(target_id)
            await reply_or_edit(event, fmt("👥 فك كتم مشرف", [f"✅ تم فك كتم المشرف `{target_id}`"]))
            return

        if text.startswith(".طرد"):
            target_id = target_entity = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = reply.sender_id
            else:
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    target_id, target_entity = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("👥 الطرد", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.kick_participant(chat_id, target_id)
                name = getattr(target_entity, 'first_name', str(target_id)) if target_entity else str(target_id)
                await reply_or_edit(event, fmt("👥 الطرد", [f"✅ تم طرد: {name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 الطرد", [f"❌ {e}"]))
            return

        if text.startswith(".اضافة "):
            username = text.split(maxsplit=1)[1].strip()
            try:
                user = await client.get_entity(username)
                await client(InviteToChannelRequest(chat_id, [user]))
                await reply_or_edit(event, fmt("👥 الإضافة", [f"✅ تم إضافة: {user.first_name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("👥 الإضافة", [f"❌ {e}"]))
            return

        if text == ".تصفية":
            banned = 0
            await reply_or_edit(event, fmt("👥 التصفية", ["⏳ جاري تصفية الأعضاء..."]))
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            admin_ids = {a.id for a in admins}
            async for user in client.iter_participants(chat_id):
                if user.id not in admin_ids and user.id != owner_id:
                    try:
                        await client.edit_permissions(chat_id, user.id, view_messages=False)
                        banned += 1
                        await asyncio.sleep(0.3)
                    except:
                        pass
            await reply_or_edit(event, fmt("👥 التصفية", [f"✅ تم حظر {banned} عضو"]))
            return

        # ══════════════════════════════════════
        #    🔑 نقل الملكية
        # ══════════════════════════════════════

        if text.startswith(".نقل_ملكية "):
            parts = text.split(maxsplit=1)
            target_id, _ = await get_user_from_input(parts[1], chat_id)
            if not target_id:
                await reply_or_edit(event, fmt("🔑 نقل الملكية", ["❌ مستخدم غير صالح!"]))
                return
            await transfer_ownership(chat_id, target_id, event)
            return

        # ══════════════════════════════════════
        #    🔒 أوامر الحماية
        # ══════════════════════════════════════

        if text.startswith(".منع "):
            word = text.split(maxsplit=1)[1].strip()
            custom_banned_words.setdefault(chat_id, set()).add(word)
            await reply_or_edit(event, fmt("🔒 الحماية", [f"✅ تم منع كلمة: {word}"]))
            return

        if text.startswith(".حذف_منع "):
            word = text.split(maxsplit=1)[1].strip()
            if chat_id in custom_banned_words:
                custom_banned_words[chat_id].discard(word)
            await reply_or_edit(event, fmt("🔒 الحماية", [f"✅ تم إلغاء منع: {word}"]))
            return

        if text == ".قائمة_المنع":
            words = list(custom_banned_words.get(chat_id, []))
            items = [f"• {w}" for w in words] if words else ["لا توجد كلمات ممنوعة"]
            await reply_or_edit(event, fmt("🔒 الكلمات الممنوعة", items))
            return

        if text == ".قفل_روابط":
            links_locked.add(chat_id)
            await reply_or_edit(event, fmt("🔒 الحماية", ["✅ تم قفل الروابط"]))
            return

        if text == ".فتح_روابط":
            links_locked.discard(chat_id)
            await reply_or_edit(event, fmt("🔒 الحماية", ["✅ تم فتح الروابط"]))
            return

        if text.startswith(".قفل "):
            media_type = text.split(maxsplit=1)[1]
            locked_media.setdefault(chat_id, set()).add(media_type)
            await reply_or_edit(event, fmt("🔒 الحماية", [f"✅ تم قفل: {media_type}"]))
            return

        if text.startswith(".فتح "):
            media_type = text.split(maxsplit=1)[1]
            if chat_id in locked_media:
                locked_media[chat_id].discard(media_type)
            await reply_or_edit(event, fmt("🔒 الحماية", [f"✅ تم فتح: {media_type}"]))
            return

        if text == ".قائمة_القفل":
            locks = list(locked_media.get(chat_id, []))
            items = [f"• {l}" for l in locks] if locks else ["لا يوجد قفل"]
            await reply_or_edit(event, fmt("🔒 الميديا المقفولة", items))
            return

        # ══ منع التصفية ══
        if text.startswith(".منع_تصفية"):
            parts = text.split(maxsplit=1)
            threshold = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            anti_purge_enabled[chat_id] = threshold
            await reply_or_edit(event, fmt("🔒 منع التصفية", [
                f"✅ تم تفعيل منع التصفية",
                f"📊 الحد: {threshold} إجراء",
                "أي مشرف يطرد/يحظر أكثر من الحد",
                "سيتم تنزيله من الإشراف فوراً"
            ]))
            return

        if text == ".الغاء_منع_تصفية":
            anti_purge_enabled.pop(chat_id, None)
            admin_action_count.pop(chat_id, None)
            await reply_or_edit(event, fmt("🔒 منع التصفية", ["✅ تم إلغاء منع التصفية"]))
            return

        # ══════════════════════════════════════
        #    ⚙️ إعدادات الجروب
        # ══════════════════════════════════════

        if text.startswith(".وصف "):
            desc = text.split(maxsplit=1)[1]
            try:
                from telethon.tl.functions.messages import EditChatAboutRequest
                await client(EditChatAboutRequest(chat_id, desc))
                await reply_or_edit(event, fmt("⚙️ الجروب", ["✅ تم تغيير الوصف"]))
            except Exception as e:
                await reply_or_edit(event, fmt("⚙️ الجروب", [f"❌ {e}"]))
            return

        if text == ".صورةمجموعة" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.photo:
                try:
                    photo = await client.download_media(reply.photo)
                    f = await client.upload_file(photo)
                    await client(EditPhotoRequest(channel=chat_id,
                                                  photo=InputChatUploadedPhoto(f)))
                    await reply_or_edit(event, fmt("⚙️ الجروب", ["✅ تم تغيير الصورة"]))
                    os.remove(photo)
                except Exception as e:
                    await reply_or_edit(event, fmt("⚙️ الجروب", [f"❌ {e}"]))
            else:
                await reply_or_edit(event, fmt("⚙️ الجروب", ["❌ رد على صورة!"]))
            return

        if text == ".المشرفين":
            try:
                admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
                items  = [f"• {a.first_name} (@{a.username or 'لا يوجد'})" for a in admins]
                await reply_or_edit(event, fmt(f"👮 المشرفين ({len(admins)})", items))
            except Exception as e:
                await reply_or_edit(event, fmt("👮 المشرفين", [f"❌ {e}"]))
            return

        if text == ".رابط_الدعوة":
            try:
                invite = await client(ExportChatInviteRequest(chat_id))
                await reply_or_edit(event, fmt("🔗 رابط الدعوة", [invite.link]))
            except Exception as e:
                await reply_or_edit(event, fmt("🔗 رابط الدعوة", [f"❌ {e}"]))
            return

        if text == ".منشن_الكل":
            try:
                mentions = []
                async for user in client.iter_participants(chat_id):
                    if not user.bot and len(mentions) < 50:
                        mentions.append(f"[{user.first_name}](tg://user?id={user.id})")
                await event.respond(" ".join(mentions), parse_mode='markdown')
            except Exception as e:
                await reply_or_edit(event, fmt("📢 المنشن", [f"❌ {e}"]))
            return

        if text == ".فحص_الاعضاء":
            total = bots = deleted = 0
            async for user in client.iter_participants(chat_id):
                total += 1
                if user.bot: bots += 1
                if user.deleted: deleted += 1
            await reply_or_edit(event, fmt("📊 إحصائيات الأعضاء", [
                f"👥 الإجمالي: {total}",
                f"🤖 البوتات: {bots}",
                f"👻 المحذوفة: {deleted}",
                f"🧑 الفعليين: {total - bots - deleted}"
            ]))
            return

        if text == ".تصدير_الاعضاء":
            members = []
            async for user in client.iter_participants(chat_id):
                members.append({'id': user.id, 'name': user.first_name,
                                 'username': user.username or '', 'bot': user.bot})
            fname = f"members_{chat_id}.json"
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(members, f, ensure_ascii=False, indent=2)
            await client.send_file(chat_id, fname,
                                    caption=fmt("📋 تصدير الأعضاء", [f"✅ {len(members)} عضو"]))
            os.remove(fname)
            return

        if text == ".حالة_الجروب":
            try:
                chat    = await client.get_entity(chat_id)
                admins  = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
                ap_status = f"✅ مفعّل (حد: {anti_purge_enabled[chat_id]})" if chat_id in anti_purge_enabled else "❌ معطّل"
                await reply_or_edit(event, fmt("📊 معلومات الجروب", [
                    f"📌 الاسم: {chat.title}",
                    f"🆔 ID: `{chat.id}`",
                    f"👥 الأعضاء: {getattr(chat, 'participants_count', '?')}",
                    f"👮 المشرفين: {len(admins)}",
                    f"🔒 منع التصفية: {ap_status}"
                ]))
            except Exception as e:
                await reply_or_edit(event, fmt("📊 معلومات الجروب", [f"❌ {e}"]))
            return

        if text == ".انشاءمجموعات":
            created = failed = 0
            status_msg = await event.respond(fmt("⚙️ إنشاء المجموعات", ["⏳ جاري الإنشاء..."]))
            for i in range(1, 11):
                try:
                    await client(CreateChannelRequest(
                        title=f"مجموعة {i}",
                        about=f"تم الإنشاء تلقائياً - {datetime.now().strftime('%Y-%m-%d')}",
                        megagroup=True
                    ))
                    created += 1
                    await asyncio.sleep(2)
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except:
                    failed += 1
            try:
                await status_msg.edit(fmt("⚙️ إنشاء المجموعات", [
                    f"✅ تم إنشاء: {created}",
                    f"❌ فشل: {failed}"
                ]))
            except:
                pass
            return

        # ══════════════════════════════════════
        #    🖼 الملف الشخصي
        # ══════════════════════════════════════

        if text == ".صورتي" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.photo:
                try:
                    photo = await client.download_media(reply.photo)
                    await client(UpdateProfileRequest())
                    await client.upload_file(photo)
                    await reply_or_edit(event, fmt("🖼 الملف الشخصي", ["✅ تم تغيير الصورة"]))
                    os.remove(photo)
                except Exception as e:
                    await reply_or_edit(event, fmt("🖼 الملف الشخصي", [f"❌ {e}"]))
            return

        if text.startswith(".اسمي "):
            new_name = text.split(maxsplit=1)[1].strip()
            parts    = new_name.split(maxsplit=1)
            try:
                await client(UpdateProfileRequest(
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else ""
                ))
                await reply_or_edit(event, fmt("🖼 الملف الشخصي", [f"✅ تم تغيير الاسم إلى: {new_name}"]))
            except Exception as e:
                await reply_or_edit(event, fmt("🖼 الملف الشخصي", [f"❌ {e}"]))
            return

        if text.startswith(".صوت "):
            url = text.split(maxsplit=1)[1].strip()
            try:
                await reply_or_edit(event, fmt("📥 التحميل", ["⏳ جاري التحميل..."]))
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            fname = "audio_temp.mp3"
                            with open(fname, 'wb') as f:
                                f.write(data)
                            await client.send_file(chat_id, fname, voice_note=True)
                            os.remove(fname)
                            await event.delete()
                        else:
                            await reply_or_edit(event, fmt("📥 التحميل", ["❌ فشل التحميل"]))
            except Exception as e:
                await reply_or_edit(event, fmt("📥 التحميل", [f"❌ {e}"]))
            return

        if text.startswith(".ارسال_ملف "):
            url = text.split(maxsplit=1)[1].strip()
            try:
                await reply_or_edit(event, fmt("📥 التحميل", ["⏳ جاري التحميل..."]))
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data  = await resp.read()
                            fname = url.split('/')[-1] or "file"
                            with open(fname, 'wb') as f:
                                f.write(data)
                            await client.send_file(chat_id, fname)
                            os.remove(fname)
                            await event.delete()
                        else:
                            await reply_or_edit(event, fmt("📥 التحميل", ["❌ فشل التحميل"]))
            except Exception as e:
                await reply_or_edit(event, fmt("📥 التحميل", [f"❌ {e}"]))
            return

    # ════════════════════════════════════════
    #    مراقبة طرد/حظر الأعضاء (منع التصفية)
    # ════════════════════════════════════════

    @client.on(events.ChatAction)
    async def monitor_chat_actions(event):
        try:
            if event.user_kicked or event.user_left:
                await check_anti_purge(event, "kick")
        except Exception as e:
            logging.error(f"monitor_chat_actions error: {e}")

    # ════════════════════════════════════════
    #         حلقة الـ Keep Alive
    # ════════════════════════════════════════

    print("⚡ اليوزربوت جاهز ويعمل!")

    while keep_alive:
        try:
            if not client.is_connected():
                await asyncio.sleep(5)
                try:
                    await client.connect()
                    if await client.is_user_authorized():
                        print("✅ تم إعادة الاتصال!")
                    else:
                        break
                except Exception as e:
                    logging.error(f"reconnect error: {e}")
                    await asyncio.sleep(10)
            else:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"keep_alive error: {e}")
            await asyncio.sleep(10)

    print("🛑 تم إيقاف اليوزربوت")
