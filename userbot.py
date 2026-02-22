import os
import re
import asyncio
import logging
import json
from datetime import datetime
from telethon import events, TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError
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

# ═══════════════════════════════════════════════
# دالة الإطار - مناسبة للعربية (اتجاه يمين لشمال)
# ═══════════════════════════════════════════════
def box(title: str, lines: list) -> str:
    """إطار عربي مناسب للـ RTL"""
    body = "\n".join(f"  ◈ {l}" for l in lines)
    return f"✦ {title}\n{'━' * 26}\n{body}\n{'━' * 26}"


COMMANDS_TEXT = """✦ 📋 قائمة الأوامر الكاملة
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 التحكم في البوت
  ◈ تشغيل         .شغل
  ◈ إيقاف         .وقف
  ◈ الحالة        .حالة
  ◈ إغلاق نهائي   .اغلق

━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 التخزين والصندوق
  ◈ ربط مجموعة       .صندوق [لينك/ID]
  ◈ حالة الصندوق     .صندوق_حالة

━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 معلومات
  ◈ معلوماتي              .انا
  ◈ كشف مستخدم (رد)      .هوية
  ◈ إحصائيات             .احصاء
  ◈ ترجمة                .رجم [نص]

━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 الإذاعة
  ◈ للكل             .بث [رسالة]
  ◈ للخاص            .بث_خاص [رسالة]
  ◈ للجروبات         .بث_جروب [رسالة]
  ◈ للقنوات          .بث_قناة [رسالة]
  ◈ صورة (رد)        .بث_صورة
  ◈ رسالة متكررة     .كرر [عدد] [رسالة]

━━━━━━━━━━━━━━━━━━━━━━━━━━
🗑️ الحذف
  ◈ حذف رسالة (رد)        .امسح
  ◈ حذف آخر 100 رسالة    .امسح_كل
  ◈ تنظيف محادثة خاصة    .نظف

━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 الترحيب
  ◈ تفعيل           .ترحيب_شغل
  ◈ إيقاف           .ترحيب_وقف
  ◈ الحالة          .ترحيب_حالة
  ◈ تغيير النص      .ترحيب_نص [النص]
  ◈ إضافة صورة (رد) .ترحيب_صورة
  ◈ إزالة الصورة    .ترحيب_بلا_صورة

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 الردود التلقائية
  ◈ إضافة فلتر      .اضف_فلتر [كلمة] [رد]
  ◈ حذف فلتر        .احذف_فلتر [كلمة]
  ◈ الفلاتر         .الفلاتر
  ◈ رد تلقائي       .اضف_رد [كلمة] [رد]
  ◈ رد بملصق (رد)   .اضف_رد_ملصق [كلمة]
  ◈ حذف رد          .احذف_رد [كلمة]

━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 إدارة الأعضاء
  ◈ حظر        .حظر (رد/@/ID)
  ◈ فك حظر     .فك_حظر (رد/@/ID)
  ◈ كتم        .كتم (رد/@/ID)
  ◈ فك كتم     .فك_كتم (رد/@/ID)
  ◈ كتم مشرف (رد)      .كتم_مشرف
  ◈ فك كتم مشرف (رد)   .فك_كتم_مشرف
  ◈ طرد        .طرد (رد/@/ID)
  ◈ إضافة      .اضف_عضو [@يوزر]
  ◈ حظر الكل   .حظر_الكل

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 الملكية
  ◈ نقل الملكية   .نقل_ملكية [ID/@]

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 الحماية
  ◈ منع كلمة          .اضف_محظور [كلمة]
  ◈ رفع منع            .احذف_محظور [كلمة]
  ◈ الكلمات المحظورة   .المحظورات
  ◈ قفل روابط         .قفل_رابط
  ◈ فتح روابط         .فتح_رابط
  ◈ قفل ميديا         .قفل_ميديا [نوع]
  ◈ فتح ميديا         .فتح_ميديا [نوع]
  ◈ قائمة القفل       .قائمة_القفل
  ◈ تفعيل ضد التصفية  .ضد_تصفية [عدد]
  ◈ إلغاء ضد التصفية  .الغ_تصفية

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ إعدادات الجروب
  ◈ تغيير الوصف      .وصف [نص]
  ◈ صورة الجروب (رد) .صورة_جروب
  ◈ المشرفين         .المشرفين
  ◈ رابط الدعوة      .رابط_دعوة
  ◈ منشن الكل        .منشن_كل
  ◈ الأعضاء          .اعضاء
  ◈ تصدير الأعضاء    .تصدير_اعضاء
  ◈ حالة الجروب      .جروب_حالة
  ◈ إنشاء جروبات     .انشاء_جروبات

━━━━━━━━━━━━━━━━━━━━━━━━━━
🖼 الملف الشخصي
  ◈ تغيير الصورة (رد) .صورتي
  ◈ تغيير الاسم       .اسمي [الاسم]
  ◈ إرسال صوت         .ارسل_صوت [رابط]
  ◈ إرسال ملف         .ارسل_ملف [رابط]
━━━━━━━━━━━━━━━━━━━━━━━━━━"""


async def start_userbot(client: TelegramClient, target_chat, user_data_store):
    print(f"✅ تيلثون شغال على: {user_data_store['phone']}")

    try:
        if not client.is_connected():
            await client.connect()
        me = await client.get_me()
        if not me:
            print("❌ فشل get_me")
            return
    except Exception as e:
        print(f"❌ فشل بدء اليوزربوت: {e}")
        return

    owner_id = me.id
    print(f"✅ {me.first_name} | ID: {owner_id}")

    # ═══ المتغيرات ═══
    bot_enabled         = True
    keep_alive          = True
    welcome_enabled     = True
    welcome_image_path  = None
    welcome_sent        = set()
    target_chat_entity  = None   # مجموعة التخزين

    filters_dict            = {}
    custom_banned_words     = {}
    locked_media            = {}
    global_replies          = {}
    global_replies_stickers = {}
    muted_admins            = {}   # {chat_id: set(user_ids)}
    muted_users             = {}   # {chat_id: set(user_ids)}
    links_locked            = set()
    anti_purge_enabled      = {}   # {chat_id: threshold}
    admin_action_count      = {}   # {chat_id: {admin_id: count}}

    welcome_text = (
        "اهلاً وسهلاً بيك 🔥\n"
        "سيب رسالتك هنا وهنرد عليك في أقرب وقت 💬\n"
        f"[القناة الرسمية]({OFFICIAL_CHANNEL_LINK})"
    )

    # ════════════════════════════
    #       الدوال المساعدة
    # ════════════════════════════

    async def is_admin(chat_id, user_id):
        try:
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            return any(a.id == user_id for a in admins)
        except:
            return False

    async def get_target(text_arg, event):
        """يرجع (user_id, entity) من رد أو @يوزر أو ID"""
        if event.is_reply:
            r = await event.get_reply_message()
            return r.sender_id, await r.get_sender()
        parts = text_arg.split(maxsplit=1)
        if len(parts) > 1:
            val = parts[1].strip().lstrip('@')
            try:
                if val.isdigit():
                    return int(val), None
                e = await client.get_entity(val)
                return e.id, e
            except:
                pass
        return None, None

    def contains_banned_word(text, chat_id):
        t = text.lower()
        return (any(w in t for w in GLOBAL_BANNED_WORDS) or
                any(w in t for w in custom_banned_words.get(chat_id, [])))

    def has_link(text):
        return bool(re.search(r'(https?://|www\.|t\.me/|telegram\.me/|@\w)', text, re.I))

    async def safe_edit(event, text):
        try:
            await event.edit(text, parse_mode='markdown')
        except:
            try:
                await event.respond(text, parse_mode='markdown')
            except Exception as e:
                logging.error(f"safe_edit: {e}")

    # ════════════════════════════
    #        نظام الـ INBOX
    # ════════════════════════════

    async def inbox_caption(sender, chat, text, src):
        fname = getattr(sender, 'first_name', '') or ''
        lname = getattr(sender, 'last_name', '') or ''
        name  = f"{fname} {lname}".strip() or "مجهول"
        uname = getattr(sender, 'username', None)
        sid   = getattr(sender, 'id', None)
        cname = getattr(chat, 'title', '') if chat and hasattr(chat, 'title') else ''

        labels = {"private": "💬 رسالة خاصة", "mention": "📢 منشن", "reply": "↩️ رد على رسالتك"}
        label  = labels.get(src, "📩 رسالة")
        now    = datetime.now().strftime('%H:%M  %d/%m/%Y')

        lines = [
            f"【 {label} 】",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"👤  **{name}**",
        ]
        if uname: lines.append(f"🔗  @{uname}")
        if sid:   lines.append(f"🆔  `{sid}`")
        if cname: lines.append(f"🏠  {cname}")
        if text and text.strip():
            lines.append(f"━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"📝  {text[:300]}{'...' if len(text)>300 else ''}")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🕐  {now}")
        return "\n".join(lines)

    async def inbox_button(sender):
        from telethon.tl.types import KeyboardButtonUrl, ReplyInlineMarkup, KeyboardButtonRow
        sid   = getattr(sender, 'id', None)
        uname = getattr(sender, 'username', None)
        fname = getattr(sender, 'first_name', '') or 'المستخدم'
        if not sid:
            return None
        url = f"https://t.me/{uname}" if uname else f"tg://user?id={sid}"
        return ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[
            KeyboardButtonUrl(text=f"💬 راسل {fname}", url=url)
        ])])

    async def push_to_inbox(event, src):
        """يبعت الرسالة لمجموعة التخزين"""
        if not target_chat_entity:
            return
        try:
            sender  = await event.get_sender()
            chat    = await event.get_chat()
            cap     = await inbox_caption(sender, chat, event.raw_text or "", src)
            markup  = await inbox_button(sender)
            # نستخدم الـ ID مباشرة مش الـ entity
            inbox_id = target_chat_entity if isinstance(target_chat_entity, int) else target_chat_entity.id
            if event.media:
                await client.send_file(
                    inbox_id, event.media,
                    caption=cap, reply_markup=markup, parse_mode='markdown'
                )
            else:
                await client.send_message(
                    inbox_id, cap,
                    reply_markup=markup, parse_mode='markdown'
                )
        except Exception as e:
            logging.error(f"push_to_inbox error: {e}")
            print(f"❌ inbox error: {e}")

    # ════════════════════════════
    #       منع التصفية
    # ════════════════════════════

    async def anti_purge_check(chat_id, acting_admin_id):
        if chat_id not in anti_purge_enabled:
            return
        if not acting_admin_id or acting_admin_id == owner_id:
            return
        if not await is_admin(chat_id, acting_admin_id):
            return

        threshold = anti_purge_enabled[chat_id]
        admin_action_count.setdefault(chat_id, {})
        admin_action_count[chat_id][acting_admin_id] = \
            admin_action_count[chat_id].get(acting_admin_id, 0) + 1
        count = admin_action_count[chat_id][acting_admin_id]

        if count >= threshold:
            admin_action_count[chat_id][acting_admin_id] = 0
            try:
                await client(EditAdminRequest(
                    channel=chat_id, user_id=acting_admin_id,
                    admin_rights=ChatAdminRights(
                        change_info=False, post_messages=False, edit_messages=False,
                        delete_messages=False, ban_users=False, invite_users=False,
                        pin_messages=False, add_admins=False, anonymous=False,
                        manage_call=False, other=False
                    ), rank=""
                ))
                try:
                    ent  = await client.get_entity(acting_admin_id)
                    name = ent.first_name or str(acting_admin_id)
                except:
                    name = str(acting_admin_id)

                now = datetime.now().strftime('%H:%M  %d/%m/%Y')
                await client.send_message(chat_id,
                    f"【 ⚠️ تحذير: محاولة تصفية 】\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤  المشرف: **{name}** (`{acting_admin_id}`)\n"
                    f"📊  عدد الإجراءات: {count}\n"
                    f"🚫  تم تنزيله من الإشراف فوراً\n"
                    f"🕐  {now}",
                    parse_mode='markdown'
                )
            except Exception as e:
                logging.error(f"anti_purge: {e}")

    # ════════════════════════════
    #       نقل الملكية
    # ════════════════════════════

    async def do_transfer(chat_id, new_owner_id, event):
        try:
            new_owner = await client.get_entity(new_owner_id)
        except Exception as e:
            await safe_edit(event, box("🔑 نقل الملكية", [f"❌ مستخدم غير موجود: {e}"]))
            return

        try:
            await client(GetParticipantRequest(chat_id, new_owner_id))
        except UserNotParticipantError:
            try:
                await client(InviteToChannelRequest(chat_id, [new_owner]))
                await asyncio.sleep(2)
            except Exception as e:
                await safe_edit(event, box("🔑 نقل الملكية", [f"❌ فشل الإضافة: {e}"]))
                return

        await safe_edit(event, box("🔑 نقل الملكية", [
            f"المستخدم: {new_owner.first_name}",
            "⚠️  لا يمكن التراجع عن هذا الإجراء",
            "أرسل كلمة سر 2FA للتأكيد",
            "أو .الغ للإلغاء"
        ]))

        try:
            resp = await client.wait_for(
                events.NewMessage(from_users=owner_id, chats=event.chat_id), timeout=120
            )
        except asyncio.TimeoutError:
            await event.respond(box("🔑 نقل الملكية", ["⏰ انتهت المهلة - تم الإلغاء"]))
            return

        pwd = resp.raw_text.strip()
        try: await resp.delete()
        except: pass

        if pwd == ".الغ":
            await event.respond(box("🔑 نقل الملكية", ["🛑 تم الإلغاء"]))
            return

        try:
            from telethon.tl.functions.account import GetPasswordRequest, CheckPasswordRequest
            from telethon.password import compute_check
            from telethon.tl.functions.channels import EditCreatorRequest

            p = await client(GetPasswordRequest())
            await client(CheckPasswordRequest(password=compute_check(p, pwd)))

            full = ChatAdminRights(
                change_info=True, post_messages=True, edit_messages=True,
                delete_messages=True, ban_users=True, invite_users=True,
                pin_messages=True, add_admins=True, anonymous=False,
                manage_call=True, other=True, manage_topics=True
            )
            await client(EditAdminRequest(channel=chat_id, user_id=new_owner_id,
                                          admin_rights=full, rank="مالك"))
            p2 = await client(GetPasswordRequest())
            await client(EditCreatorRequest(channel=chat_id, user_id=new_owner_id,
                                            password=compute_check(p2, pwd)))
            await event.respond(box("🔑 نقل الملكية", [
                f"✅ تم النقل بنجاح!",
                f"المالك الجديد: {new_owner.first_name}",
                f"🆔 `{new_owner.id}`"
            ]))
        except Exception as e:
            await event.respond(box("🔑 نقل الملكية", [f"❌ خطأ: {e}"]))

    # ════════════════════════════════════════════════════
    #                 Handler الرئيسي
    # ════════════════════════════════════════════════════

    @client.on(events.NewMessage)
    async def handle_all(event):
        nonlocal welcome_enabled, welcome_image_path, welcome_text
        nonlocal bot_enabled, keep_alive, target_chat_entity

        text      = event.raw_text or ""
        chat_id   = event.chat_id
        sender_id = event.sender_id

        # ══════════════════════════════════
        # 1) رسائل واردة (مش منك)
        # ══════════════════════════════════
        if not event.out and sender_id != owner_id:
            try:
                sender = await event.get_sender()
                if sender and not getattr(sender, 'bot', False):
                    if event.is_private:
                        # رسالة خاصة → صندوق
                        await push_to_inbox(event, "private")

                        # ترحيب تلقائي
                        if welcome_enabled and sender_id not in welcome_sent:
                            welcome_sent.add(sender_id)
                            try:
                                if welcome_image_path and os.path.exists(welcome_image_path):
                                    await client.send_file(chat_id, welcome_image_path,
                                                           caption=welcome_text, parse_mode='markdown')
                                else:
                                    await event.respond(welcome_text, parse_mode='markdown')
                            except:
                                pass

                    elif event.is_group or event.is_channel:
                        # منشن أو رد على رسالتك → صندوق
                        if event.mentioned:
                            await push_to_inbox(event, "mention")
                        elif event.is_reply:
                            try:
                                replied = await event.get_reply_message()
                                if replied and replied.sender_id == owner_id:
                                    await push_to_inbox(event, "reply")
                            except:
                                pass

                        # حماية الجروب
                        if bot_enabled and event.is_group:
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
                                if chat_id in links_locked and has_link(text):
                                    try: await event.delete()
                                    except: pass
                                    return
                                if chat_id in locked_media:
                                    lk = locked_media[chat_id]
                                    if (('صور' in lk and event.photo) or
                                        ('فيديو' in lk and event.video) or
                                        ('ملصقات' in lk and event.sticker) or
                                        ('ملفات' in lk and event.document
                                             and not event.sticker and not event.video and not event.audio) or
                                        ('صوت' in lk and (event.audio or event.voice)) or
                                        ('gif' in lk and event.gif)):
                                        try: await event.delete()
                                        except: pass
                                        return

            except Exception as e:
                logging.error(f"incoming handler: {e}")

            # ردود تلقائية
            if text in filters_dict:
                await event.respond(filters_dict[text])
            if text.lower() in global_replies:
                await event.respond(global_replies[text.lower()])
            elif text.lower() in global_replies_stickers:
                await client.send_file(chat_id, global_replies_stickers[text.lower()], reply_to=event.id)
            return  # ← مهم: الرسائل الواردة تنتهي هنا

        # ══════════════════════════════════
        # 2) أوامر صاحب الحساب فقط
        # ══════════════════════════════════
        if not event.out:
            return
        if not text.startswith('.'):
            return

        # ── أوامر تعمل حتى لو البوت مُعطَّل ──
        if text == ".شغل":
            bot_enabled = True
            await safe_edit(event, box("🔧 التحكم", ["✅ تم تفعيل البوت", "🟢 كل الميزات شغالة"]))
            return

        if text == ".وقف":
            bot_enabled = False
            await safe_edit(event, box("🔧 التحكم", ["⏸️ تم تعطيل البوت", "🔴 الميزات متوقفة"]))
            return

        if text == ".حالة":
            s  = "🟢 مفعّل" if bot_enabled else "🔴 معطّل"
            sb = f"✅ {target_chat_entity.title}" if target_chat_entity else "❌ غير مربوط"
            await safe_edit(event, box("🔧 الحالة", [
                f"البوت: {s}",
                f"الصندوق: {sb}",
                f"الحساب: {me.first_name}",
                f"🕐 {datetime.now().strftime('%H:%M  %d/%m/%Y')}"
            ]))
            return

        if text == ".اغلق":
            await safe_edit(event, box("🔧 التحكم", ["🛑 جاري الإيقاف..."]))
            await asyncio.sleep(1)
            keep_alive = False
            await client.disconnect()
            return

        if text == ".الاوامر":
            await safe_edit(event, COMMANDS_TEXT)
            return

        # ── باقي الأوامر تحتاج البوت مفعّل ──
        if not bot_enabled:
            return

        # ════════════════════════════
        # 📦 التخزين والـ Inbox
        # ════════════════════════════

        if text.startswith(".صندوق"):
            args = text.split(maxsplit=1)
            if len(args) < 2:
                sb = f"✅ {getattr(target_chat_entity,'title', target_chat_entity)}" if target_chat_entity else "❌ غير مربوط"
                await safe_edit(event, box("📦 الصندوق", [
                    "الاستخدام: .صندوق [لينك أو ID]",
                    f"الحالة: {sb}"
                ]))
                return
            try:
                await safe_edit(event, box("📦 الصندوق", ["⏳ جاري الربط..."]))
                inp = args[1].strip()
                # جرب تحمل الـ entity من الـ dialogs الأول
                ent = None
                async for d in client.iter_dialogs():
                    if (inp.lstrip('-').isdigit() and d.id == int(inp)) or \
                       (hasattr(d.entity, 'username') and d.entity.username and
                        inp.lstrip('@').lower() == d.entity.username.lower()):
                        ent = d.entity
                        break
                # لو مش في الـ dialogs جرب get_entity
                if not ent:
                    ent = await client.get_entity(inp)
                target_chat_entity = ent
                await safe_edit(event, box("📦 الصندوق", [
                    "✅ تم الربط بنجاح!",
                    f"المجموعة: {ent.title}",
                    f"ID: {ent.id}",
                    "الرسائل ستُخزَّن تلقائياً 📥"
                ]))
            except Exception as e:
                await safe_edit(event, box("📦 الصندوق", [
                    "❌ فشل الربط!",
                    "تأكد إنك عضو في المجموعة",
                    f"الخطأ: {e}"
                ]))
            return

        if text == ".صندوق_حالة":
            if target_chat_entity:
                await safe_edit(event, box("📦 الصندوق", [
                    f"✅ مربوط: {target_chat_entity.title}",
                    f"🆔 {target_chat_entity.id}"
                ]))
            else:
                await safe_edit(event, box("📦 الصندوق", [
                    "❌ غير مربوط",
                    "استخدم: .صندوق [لينك أو ID]"
                ]))
            return

        # ════════════════════════════
        # 👤 معلومات
        # ════════════════════════════

        if text == ".انا":
            await safe_edit(event, box("👤 معلوماتي", [
                f"الاسم: {me.first_name} {me.last_name or ''}",
                f"🆔 `{me.id}`",
                f"يوزر: @{me.username or 'لا يوجد'}"
            ]))
            return

        if text == ".هوية" and event.is_reply:
            r = await event.get_reply_message()
            s = await r.get_sender()
            if s:
                await safe_edit(event, box("👤 هوية المستخدم", [
                    f"الاسم: {s.first_name} {getattr(s,'last_name','') or ''}",
                    f"?? `{s.id}`",
                    f"يوزر: @{s.username or 'لا يوجد'}",
                    f"بوت: {'نعم' if s.bot else 'لا'}"
                ]))
            return

        if text == ".احصاء":
            p = g = c = 0
            async for d in client.iter_dialogs():
                if d.is_user: p += 1
                elif d.is_group: g += 1
                elif d.is_channel: c += 1
            await safe_edit(event, box("📊 الإحصائيات", [
                f"💬 خاص: {p}",
                f"👥 جروبات: {g}",
                f"📢 قنوات: {c}",
                f"📊 الإجمالي: {p+g+c}"
            ]))
            return

        if text.startswith(".رجم "):
            to_tr = text[5:].strip()
            try:
                tr = GoogleTranslator(source='auto', target='ar').translate(to_tr)
                if tr == to_tr:
                    tr = GoogleTranslator(source='auto', target='en').translate(to_tr)
                await safe_edit(event, box("🌐 الترجمة", [f"الأصل: {to_tr}", f"الترجمة: {tr}"]))
            except Exception as e:
                await safe_edit(event, box("🌐 الترجمة", [f"❌ {e}"]))
            return

        # ════════════════════════════
        # 📢 الإذاعة
        # ════════════════════════════

        if text.startswith((".بث", ".بث_خاص", ".بث_جروب", ".بث_قناة")):
            args = text.split(maxsplit=1)
            if len(args) < 2: return
            cmd, msg = args[0], args[1]
            sent = failed = 0
            await safe_edit(event, box("📢 الإذاعة", ["⏳ جاري الإرسال..."]))
            async for d in client.iter_dialogs():
                try:
                    ok = (cmd == ".بث" or
                          (cmd == ".بث_خاص" and d.is_user) or
                          (cmd == ".بث_جروب" and d.is_group) or
                          (cmd == ".بث_قناة" and d.is_channel))
                    if ok:
                        await client.send_message(d.id, msg)
                        sent += 1
                        await asyncio.sleep(1)
                except:
                    failed += 1
            await safe_edit(event, box("📢 الإذاعة", [f"✅ أُرسلت: {sent}", f"❌ فشلت: {failed}"]))
            return

        if text == ".بث_صورة" and event.is_reply:
            r = await event.get_reply_message()
            if not r.photo:
                await safe_edit(event, box("📢 الإذاعة", ["❌ رد على صورة!"]))
                return
            sent = failed = 0
            await safe_edit(event, box("📢 الإذاعة", ["⏳ جاري إرسال الصورة..."]))
            async for d in client.iter_dialogs():
                try:
                    await client.send_file(d.id, r.photo, caption=r.text or "")
                    sent += 1
                    await asyncio.sleep(1)
                except:
                    failed += 1
            await safe_edit(event, box("📢 الإذاعة", [f"✅ {sent}", f"❌ {failed}"]))
            return

        if text.startswith(".كرر "):
            args = text.split(maxsplit=2)
            if len(args) < 3 or not args[1].isdigit(): return
            n = min(int(args[1]), 50)
            for _ in range(n):
                try:
                    await client.send_message(chat_id, args[2])
                    await asyncio.sleep(0.5)
                except: break
            return

        # ════════════════════════════
        # 🗑️ الحذف
        # ════════════════════════════

        if text == ".امسح" and event.is_reply:
            try:
                r = await event.get_reply_message()
                await r.delete()
                await event.delete()
            except Exception as e:
                await safe_edit(event, box("🗑️ الحذف", [f"❌ {e}"]))
            return

        if text == ".امسح_كل":
            n = 0
            async for m in client.iter_messages(chat_id, from_user='me', limit=100):
                try:
                    await m.delete()
                    n += 1
                    await asyncio.sleep(0.1)
                except: pass
            await client.send_message(chat_id, box("🗑️ الحذف", [f"✅ تم حذف {n} رسالة"]))
            return

        if text == ".نظف" and event.is_private:
            async for m in client.iter_messages(chat_id, limit=200):
                try:
                    await m.delete()
                    await asyncio.sleep(0.05)
                except: pass
            return

        # ════════════════════════════
        # 🎉 الترحيب
        # ════════════════════════════

        if text == ".ترحيب_شغل":
            welcome_enabled = True
            await safe_edit(event, box("🎉 الترحيب", ["✅ تم تفعيل الترحيب"]))
            return

        if text == ".ترحيب_وقف":
            welcome_enabled = False
            await safe_edit(event, box("🎉 الترحيب", ["⏸️ تم إيقاف الترحيب"]))
            return

        if text == ".ترحيب_حالة":
            s   = "✅ مفعّل" if welcome_enabled else "❌ موقوف"
            img = "✅ موجودة" if welcome_image_path else "❌ لا توجد"
            await safe_edit(event, box("🎉 الترحيب", [f"الحالة: {s}", f"الصورة: {img}"]))
            return

        if text.startswith(".ترحيب_نص "):
            welcome_text = text[11:]
            await safe_edit(event, box("🎉 الترحيب", ["✅ تم تغيير النص"]))
            return

        if text == ".ترحيب_صورة" and event.is_reply:
            r = await event.get_reply_message()
            if r.photo:
                path = f"welcome_{me.id}.jpg"
                await client.download_media(r.photo, path)
                welcome_image_path = path
                await safe_edit(event, box("🎉 الترحيب", ["✅ تم تعيين الصورة"]))
            else:
                await safe_edit(event, box("🎉 الترحيب", ["❌ رد على صورة!"]))
            return

        if text == ".ترحيب_بلا_صورة":
            welcome_image_path = None
            await safe_edit(event, box("🎉 الترحيب", ["✅ تم إزالة الصورة"]))
            return

        # ════════════════════════════
        # 🔄 الردود التلقائية
        # ════════════════════════════

        if text.startswith(".اضف_فلتر "):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                filters_dict[parts[1]] = parts[2]
                await safe_edit(event, box("🔄 الفلاتر", [f"✅ تم إضافة: {parts[1]}"]))
            return

        if text.startswith(".احذف_فلتر "):
            k = text.split(maxsplit=1)[1]
            filters_dict.pop(k, None)
            await safe_edit(event, box("🔄 الفلاتر", [f"✅ تم حذف: {k}"]))
            return

        if text == ".الفلاتر":
            items = [f"{k}  ◄  {v}" for k, v in filters_dict.items()] or ["لا توجد فلاتر"]
            await safe_edit(event, box("🔄 الفلاتر", items))
            return

        if text.startswith(".اضف_رد "):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                global_replies[parts[1].lower()] = parts[2]
                await safe_edit(event, box("🔄 الردود", [f"✅ تم إضافة: {parts[1]}"]))
            return

        if text.startswith(".اضف_رد_ملصق ") and event.is_reply:
            parts = text.split(maxsplit=1)
            r = await event.get_reply_message()
            if len(parts) > 1 and r.sticker:
                global_replies_stickers[parts[1].lower()] = r.sticker
                await safe_edit(event, box("🔄 الردود", [f"✅ تم إضافة ملصق: {parts[1]}"]))
            return

        if text.startswith(".احذف_رد "):
            k = text.split(maxsplit=1)[1].lower()
            global_replies.pop(k, None)
            global_replies_stickers.pop(k, None)
            await safe_edit(event, box("🔄 الردود", [f"✅ تم حذف: {k}"]))
            return

        # ════════════════════════════
        # 👥 إدارة الأعضاء
        # ════════════════════════════

        if text.startswith(".حظر"):
            uid, ent = await get_target(text, event)
            if not uid:
                await safe_edit(event, box("👥 الحظر", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, uid, view_messages=False)
                name = getattr(ent, 'first_name', str(uid)) if ent else str(uid)
                await safe_edit(event, box("👥 الحظر", [f"✅ تم حظر: {name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 الحظر", [f"❌ {e}"]))
            return

        if text.startswith(".فك_حظر"):
            uid, ent = await get_target(text, event)
            if not uid:
                await safe_edit(event, box("👥 فك الحظر", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, uid, view_messages=True)
                name = getattr(ent, 'first_name', str(uid)) if ent else str(uid)
                await safe_edit(event, box("👥 فك الحظر", [f"✅ تم فك حظر: {name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 فك الحظر", [f"❌ {e}"]))
            return

        if text.startswith(".كتم") and not text.startswith(".كتم_مشرف"):
            uid, ent = await get_target(text, event)
            if not uid:
                await safe_edit(event, box("👥 الكتم", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, uid,
                    send_messages=False, send_media=False,
                    send_stickers=False, send_gifs=False)
                muted_users.setdefault(chat_id, set()).add(uid)
                name = getattr(ent, 'first_name', str(uid)) if ent else str(uid)
                async for m in client.iter_messages(chat_id, from_user=uid, limit=50):
                    try: await m.delete()
                    except: pass
                await safe_edit(event, box("👥 الكتم", [f"✅ تم كتم: {name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 الكتم", [f"❌ {e}"]))
            return

        if text.startswith(".فك_كتم") and not text.startswith(".فك_كتم_مشرف"):
            uid, ent = await get_target(text, event)
            if not uid:
                await safe_edit(event, box("👥 فك الكتم", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.edit_permissions(chat_id, uid,
                    send_messages=True, send_media=True,
                    send_stickers=True, send_gifs=True)
                if chat_id in muted_users:
                    muted_users[chat_id].discard(uid)
                name = getattr(ent, 'first_name', str(uid)) if ent else str(uid)
                await safe_edit(event, box("👥 فك الكتم", [f"✅ تم فك كتم: {name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 فك الكتم", [f"❌ {e}"]))
            return

        if text == ".كتم_مشرف" and event.is_reply:
            r = await event.get_reply_message()
            uid = r.sender_id
            muted_admins.setdefault(chat_id, set()).add(uid)
            async for m in client.iter_messages(chat_id, from_user=uid, limit=50):
                try: await m.delete()
                except: pass
            await safe_edit(event, box("👥 كتم مشرف", [f"✅ تم كتم المشرف `{uid}`"]))
            return

        if text == ".فك_كتم_مشرف" and event.is_reply:
            r = await event.get_reply_message()
            uid = r.sender_id
            if chat_id in muted_admins:
                muted_admins[chat_id].discard(uid)
            await safe_edit(event, box("👥 فك كتم مشرف", [f"✅ تم فك الكتم `{uid}`"]))
            return

        if text.startswith(".طرد"):
            uid, ent = await get_target(text, event)
            if not uid:
                await safe_edit(event, box("👥 الطرد", ["❌ حدد المستخدم!"]))
                return
            try:
                await client.kick_participant(chat_id, uid)
                name = getattr(ent, 'first_name', str(uid)) if ent else str(uid)
                await safe_edit(event, box("👥 الطرد", [f"✅ تم طرد: {name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 الطرد", [f"❌ {e}"]))
            return

        if text.startswith(".اضف_عضو "):
            username = text.split(maxsplit=1)[1].strip()
            try:
                u = await client.get_entity(username)
                await client(InviteToChannelRequest(chat_id, [u]))
                await safe_edit(event, box("👥 الإضافة", [f"✅ تم إضافة: {u.first_name}"]))
            except Exception as e:
                await safe_edit(event, box("👥 الإضافة", [f"❌ {e}"]))
            return

        if text == ".حظر_الكل":
            n = 0
            await safe_edit(event, box("👥 حظر الكل", ["⏳ جاري الحظر..."]))
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            admin_ids = {a.id for a in admins}
            async for u in client.iter_participants(chat_id):
                if u.id not in admin_ids and u.id != owner_id:
                    try:
                        await client.edit_permissions(chat_id, u.id, view_messages=False)
                        n += 1
                        await asyncio.sleep(0.3)
                    except: pass
            await safe_edit(event, box("👥 حظر الكل", [f"✅ تم حظر {n} عضو"]))
            return

        # ════════════════════════════
        # 🔑 نقل الملكية
        # ════════════════════════════

        if text.startswith(".نقل_ملكية "):
            parts = text.split(maxsplit=1)
            val   = parts[1].strip().lstrip('@')
            try:
                uid = int(val) if val.isdigit() else (await client.get_entity(val)).id
            except Exception as e:
                await safe_edit(event, box("🔑 نقل الملكية", [f"❌ {e}"]))
                return
            await do_transfer(chat_id, uid, event)
            return

        # ════════════════════════════
        # 🔒 الحماية
        # ════════════════════════════

        if text.startswith(".اضف_محظور "):
            w = text.split(maxsplit=1)[1].strip()
            custom_banned_words.setdefault(chat_id, set()).add(w)
            await safe_edit(event, box("🔒 الكلمات المحظورة", [f"✅ تم إضافة: {w}"]))
            return

        if text.startswith(".احذف_محظور "):
            w = text.split(maxsplit=1)[1].strip()
            if chat_id in custom_banned_words:
                custom_banned_words[chat_id].discard(w)
            await safe_edit(event, box("🔒 الكلمات المحظورة", [f"✅ تم حذف: {w}"]))
            return

        if text == ".المحظورات":
            words = list(custom_banned_words.get(chat_id, []))
            items = [f"◄  {w}" for w in words] or ["لا توجد كلمات"]
            await safe_edit(event, box("🔒 الكلمات المحظورة", items))
            return

        if text == ".قفل_رابط":
            links_locked.add(chat_id)
            await safe_edit(event, box("🔒 الحماية", ["✅ تم قفل الروابط"]))
            return

        if text == ".فتح_رابط":
            links_locked.discard(chat_id)
            await safe_edit(event, box("🔒 الحماية", ["✅ تم فتح الروابط"]))
            return

        if text.startswith(".قفل_ميديا "):
            t = text.split(maxsplit=1)[1]
            locked_media.setdefault(chat_id, set()).add(t)
            await safe_edit(event, box("🔒 الحماية", [f"✅ تم قفل: {t}"]))
            return

        if text.startswith(".فتح_ميديا "):
            t = text.split(maxsplit=1)[1]
            if chat_id in locked_media:
                locked_media[chat_id].discard(t)
            await safe_edit(event, box("🔒 الحماية", [f"✅ تم فتح: {t}"]))
            return

        if text == ".قائمة_القفل":
            lk = list(locked_media.get(chat_id, []))
            items = [f"◄  {l}" for l in lk] or ["لا يوجد قفل"]
            await safe_edit(event, box("🔒 القفل", items))
            return

        if text.startswith(".ضد_تصفية"):
            parts = text.split(maxsplit=1)
            thr = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            anti_purge_enabled[chat_id] = thr
            await safe_edit(event, box("🔒 منع التصفية", [
                "✅ تم التفعيل",
                f"الحد: {thr} إجراء",
                "أي مشرف يتجاوزه يُنزَّل فوراً"
            ]))
            return

        if text == ".الغ_تصفية":
            anti_purge_enabled.pop(chat_id, None)
            admin_action_count.pop(chat_id, None)
            await safe_edit(event, box("🔒 منع التصفية", ["✅ تم الإلغاء"]))
            return

        # ════════════════════════════
        # ⚙️ إعدادات الجروب
        # ════════════════════════════

        if text.startswith(".وصف "):
            desc = text.split(maxsplit=1)[1]
            try:
                from telethon.tl.functions.messages import EditChatAboutRequest
                await client(EditChatAboutRequest(chat_id, desc))
                await safe_edit(event, box("⚙️ الجروب", ["✅ تم تغيير الوصف"]))
            except Exception as e:
                await safe_edit(event, box("⚙️ الجروب", [f"❌ {e}"]))
            return

        if text == ".صورة_جروب" and event.is_reply:
            r = await event.get_reply_message()
            if r.photo:
                try:
                    photo = await client.download_media(r.photo)
                    f = await client.upload_file(photo)
                    await client(EditPhotoRequest(channel=chat_id,
                                                  photo=InputChatUploadedPhoto(f)))
                    await safe_edit(event, box("⚙️ الجروب", ["✅ تم تغيير الصورة"]))
                    os.remove(photo)
                except Exception as e:
                    await safe_edit(event, box("⚙️ الجروب", [f"❌ {e}"]))
            else:
                await safe_edit(event, box("⚙️ الجروب", ["❌ رد على صورة!"]))
            return

        if text == ".المشرفين":
            try:
                admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
                items  = [f"@{a.username or a.first_name}  `{a.id}`" for a in admins]
                await safe_edit(event, box(f"👮 المشرفين ({len(admins)})", items))
            except Exception as e:
                await safe_edit(event, box("👮 المشرفين", [f"❌ {e}"]))
            return

        if text == ".رابط_دعوة":
            try:
                inv = await client(ExportChatInviteRequest(chat_id))
                await safe_edit(event, box("🔗 رابط الدعوة", [inv.link]))
            except Exception as e:
                await safe_edit(event, box("🔗 رابط الدعوة", [f"❌ {e}"]))
            return

        if text == ".منشن_كل":
            try:
                mentions = []
                async for u in client.iter_participants(chat_id):
                    if not u.bot and len(mentions) < 50:
                        mentions.append(f"[{u.first_name}](tg://user?id={u.id})")
                await event.respond(" ".join(mentions), parse_mode='markdown')
            except Exception as e:
                await safe_edit(event, box("📢 المنشن", [f"❌ {e}"]))
            return

        if text == ".اعضاء":
            total = bots = deleted = 0
            async for u in client.iter_participants(chat_id):
                total += 1
                if u.bot: bots += 1
                if u.deleted: deleted += 1
            await safe_edit(event, box("📊 الأعضاء", [
                f"👥 الإجمالي: {total}",
                f"🤖 البوتات: {bots}",
                f"👻 المحذوفة: {deleted}",
                f"🧑 الفعليين: {total-bots-deleted}"
            ]))
            return

        if text == ".تصدير_اعضاء":
            members = []
            async for u in client.iter_participants(chat_id):
                members.append({'id': u.id, 'name': u.first_name,
                                 'username': u.username or '', 'bot': u.bot})
            fn = f"members_{chat_id}.json"
            with open(fn, 'w', encoding='utf-8') as f:
                json.dump(members, f, ensure_ascii=False, indent=2)
            await client.send_file(chat_id, fn,
                caption=box("📋 تصدير الأعضاء", [f"✅ {len(members)} عضو"]))
            os.remove(fn)
            return

        if text == ".جروب_حالة":
            try:
                ch     = await client.get_entity(chat_id)
                admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
                ap     = f"✅ (حد: {anti_purge_enabled[chat_id]})" if chat_id in anti_purge_enabled else "❌ معطّل"
                await safe_edit(event, box("📊 الجروب", [
                    f"📌 {ch.title}",
                    f"🆔 `{ch.id}`",
                    f"👥 {getattr(ch,'participants_count','?')} عضو",
                    f"👮 {len(admins)} مشرف",
                    f"🔒 منع التصفية: {ap}"
                ]))
            except Exception as e:
                await safe_edit(event, box("📊 الجروب", [f"❌ {e}"]))
            return

        if text == ".انشاء_جروبات":
            created = failed = 0
            sm = await event.respond(box("⚙️ الإنشاء", ["⏳ جاري إنشاء 10 مجموعات..."]))
            for i in range(1, 11):
                try:
                    await client(CreateChannelRequest(
                        title=f"مجموعة {i}",
                        about=f"أُنشئت تلقائياً  {datetime.now().strftime('%Y-%m-%d')}",
                        megagroup=True
                    ))
                    created += 1
                    await asyncio.sleep(2)
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except:
                    failed += 1
            try:
                await sm.edit(box("⚙️ الإنشاء", [f"✅ تم: {created}", f"❌ فشل: {failed}"]))
            except: pass
            return

        # ════════════════════════════
        # 🖼 الملف الشخصي
        # ════════════════════════════

        if text == ".صورتي" and event.is_reply:
            r = await event.get_reply_message()
            if r.photo:
                try:
                    from telethon.tl.functions.photos import UploadProfilePhotoRequest
                    photo = await client.download_media(r.photo)
                    uploaded = await client.upload_file(photo)
                    await client(UploadProfilePhotoRequest(file=uploaded))
                    await safe_edit(event, box("🖼 الملف الشخصي", ["✅ تم تغيير الصورة"]))
                    os.remove(photo)
                except Exception as e:
                    await safe_edit(event, box("🖼 الملف الشخصي", [f"❌ {e}"]))
            return

        if text.startswith(".اسمي "):
            parts = text.split(maxsplit=1)[1].strip().split(maxsplit=1)
            try:
                await client(UpdateProfileRequest(
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else ""
                ))
                await safe_edit(event, box("🖼 الملف الشخصي", [f"✅ تم تغيير الاسم"]))
            except Exception as e:
                await safe_edit(event, box("🖼 الملف الشخصي", [f"❌ {e}"]))
            return

        if text.startswith(".ارسل_صوت "):
            url = text.split(maxsplit=1)[1].strip()
            try:
                await safe_edit(event, box("📥 التحميل", ["⏳ جاري التحميل..."]))
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            fn   = "audio_tmp.mp3"
                            with open(fn, 'wb') as f: f.write(data)
                            await client.send_file(chat_id, fn, voice_note=True)
                            os.remove(fn)
                            await event.delete()
                        else:
                            await safe_edit(event, box("📥 التحميل", ["❌ فشل"]))
            except Exception as e:
                await safe_edit(event, box("📥 التحميل", [f"❌ {e}"]))
            return

        if text.startswith(".ارسل_ملف "):
            url = text.split(maxsplit=1)[1].strip()
            try:
                await safe_edit(event, box("📥 التحميل", ["⏳ جاري التحميل..."]))
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            fn   = url.split('/')[-1] or "file"
                            with open(fn, 'wb') as f: f.write(data)
                            await client.send_file(chat_id, fn)
                            os.remove(fn)
                            await event.delete()
                        else:
                            await safe_edit(event, box("📥 التحميل", ["❌ فشل"]))
            except Exception as e:
                await safe_edit(event, box("📥 التحميل", [f"❌ {e}"]))
            return

    # ════════════════════════════════════
    #   مراقبة طرد/حظر (منع التصفية)
    # ════════════════════════════════════

    @client.on(events.ChatAction)
    async def watch_actions(event):
        """يراقب الطرد لمنع التصفية"""
        try:
            chat_id = event.chat_id
            if chat_id not in anti_purge_enabled:
                return

            kicked = False
            try:
                kicked = event.user_kicked
            except:
                pass

            if not kicked:
                return

            # اجلب ID اللي نفذ الطرد
            acting_id = None
            try:
                action_msg = event.action_message
                if action_msg and hasattr(action_msg, 'from_id') and action_msg.from_id:
                    from telethon.tl.types import PeerUser
                    if isinstance(action_msg.from_id, PeerUser):
                        acting_id = action_msg.from_id.user_id
            except:
                pass

            if not acting_id:
                try:
                    acting_id = event.sender_id
                except:
                    pass

            if acting_id:
                await anti_purge_check(chat_id, acting_id)

        except Exception as e:
            logging.error(f"watch_actions: {e}")

    @client.on(events.NewMessage(func=lambda e: e.is_group and not e.out and bool(e.action)))
    async def watch_bans(event):
        """يراقب الحظر عبر الرسائل الإدارية"""
        try:
            chat_id = event.chat_id
            if chat_id not in anti_purge_enabled:
                return

            from telethon.tl.types import (
                MessageActionChatDeleteUser,
                MessageActionChatBannedRights
            )

            if not isinstance(event.action, (MessageActionChatDeleteUser, MessageActionChatBannedRights)):
                return

            acting_id = event.sender_id
            if acting_id and acting_id != owner_id:
                await anti_purge_check(chat_id, acting_id)

        except Exception as e:
            logging.error(f"watch_bans: {e}")

    # ════════════════════════════════════
    #          حلقة Keep Alive
    # ════════════════════════════════════

    print("⚡ اليوزربوت جاهز!")

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
                    logging.error(f"reconnect: {e}")
                    await asyncio.sleep(10)
            else:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"keep_alive: {e}")
            await asyncio.sleep(10)

    print("🛑 تم إيقاف اليوزربوت")