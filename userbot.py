import os
import asyncio
import logging
import json
from telethon import events, TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import (
    LeaveChannelRequest, EditPhotoRequest, CreateChannelRequest,
    InviteToChannelRequest, EditAdminRequest, GetParticipantRequest
)
from telethon.tl.types import (
    InputChatUploadedPhoto, ChannelParticipantsAdmins,
    ChatAdminRights
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors.rpcerrorlist import UserNotParticipantError, UserIdInvalidError
from datetime import datetime
import aiohttp
from deep_translator import GoogleTranslator

logging.basicConfig(
    filename='telthon_errors.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

OFFICIAL_CHANNEL_ID = -1002228737674
OFFICIAL_CHANNEL_LINK = "https://t.me/FY_TF"

GLOBAL_BANNED_WORDS = {
    "كس", "كسك", "كسمك", "كسم", "طيز", "طيزك", "زب", "زبي", "زبك",
    "نيك", "نيكني", "نيكك", "انيكك", "متناك", "متناكة", "منيوك", "منيوكة",
    "شرموط", "شرموطة", "شراميط", "عرص", "عرصة", "معرص", "قحبة", "قحب",
    "وسخة", "وسخ", "خول", "خولات", "لبوة", "بزاز", "بز", "احا", "اح",
    "ابن المتناكة", "ابن الشرموطة", "ابن القحبة", "ابن الوسخة",
    "بنت المتناكة", "بنت الشرموطة", "بنت القحبة", "بنت الوسخة",
    "يلعن", "يلعن ابوك", "يلعن امك", "يلعن دينك", "كسمين",
    "منايك", "منايكة", "عرصات", "لبؤة", "فشخ", "فشخك", "مفشوخ", "مفشوخة",
    "جلق", "جلقلك", "لوطي", "خنيث", "بيتش", "سكس", "sex", "porn", "xxx",
    "fuck", "bitch", "pussy", "dick", "cock", "ass", "shit",
}

async def start_userbot(client: TelegramClient, target_chat, user_data_store):
    logging.debug(f"تيلثون شغال على الحساب: {user_data_store['phone']}")
    print(f"✅ تيلثون شغال على: {user_data_store['phone']}")

    # تأكد إن الكلاينت متصل
    try:
        if not client.is_connected():
            await client.connect()
        me = await client.get_me()
        if not me:
            print(f"❌ فشل get_me - الجلسة غير صالحة")
            return
    except Exception as e:
        print(f"❌ فشل بدء اليوزربوت: {e}")
        return

    owner_id = me.id
    print(f"✅ حساب اليوزربوت: {me.first_name} | ID: {owner_id}")

    # حالة البوت
    bot_enabled = True
    keep_alive = True
    
    filters_dict = {}
    welcome_sent = set()
    welcome_enabled = True
    custom_banned_words = {}
    locked_media = {}
    global_replies = {}
    global_replies_stickers = {}
    muted_admins = {}
    muted_users = {}
    links_locked = set()

    welcome_text_template = (
        "اهلاً وسهلاً بيك 🔥\n"
        "سيب رسالتك هنا وهنرد عليك في أقرب وقت 💬\n"
        "[القناة الرسمية]({link})"
    )
    welcome_image_path = None

    async def is_admin(chat_id, user_id):
        try:
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            return any(admin.id == user_id for admin in admins)
        except:
            return False

    async def get_user_from_input(user_input, chat_id=None):
        """دالة مساعدة لجلب المستخدم من ID أو username"""
        try:
            user_input = str(user_input).strip('@')
            
            if user_input.isdigit():
                user_id = int(user_input)
                user_entity = None
                
                if chat_id:
                    try:
                        participants = await client.get_participants(chat_id, limit=1000)
                        for p in participants:
                            if p.id == user_id:
                                user_entity = p
                                break
                    except:
                        pass
                
                return user_id, user_entity
            else:
                user_entity = await client.get_entity(user_input)
                return user_entity.id, user_entity
                
        except Exception as e:
            return None, None

    def contains_banned_word(text, chat_id):
        text_lower = text.lower()
        for word in GLOBAL_BANNED_WORDS:
            if word in text_lower:
                return True
        if chat_id in custom_banned_words:
            for word in custom_banned_words[chat_id]:
                if word in text_lower:
                    return True
        return False

    def contains_link(text):
        import re
        url_pattern = r'(https?://|www\.|t\.me/|telegram\.me/|@)'
        return bool(re.search(url_pattern, text, re.IGNORECASE))

    async def reply_or_edit(event, text, **kwargs):
        """يعدّل رسالة الأمر الأصلية بدل إرسال رسالة جديدة"""
        try:
            if event.out:
                await event.edit(text, **kwargs)
            else:
                await event.respond(text, **kwargs)
        except Exception:
            try:
                await event.respond(text, **kwargs)
            except Exception as e:
                logging.error(f"فشل الرد/التعديل: {e}")

    async def transfer_ownership(chat_id, new_owner_id, event):
        try:
            try:
                new_owner = await client.get_entity(new_owner_id)
            except (UserIdInvalidError, ValueError):
                await reply_or_edit(event, "❌ المستخدم غير موجود! تأكد من الـ ID")
                return
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ في جلب بيانات المستخدم: {str(e)}")
                return

            is_member = False
            try:
                await client(GetParticipantRequest(chat_id, new_owner_id))
                is_member = True
            except UserNotParticipantError:
                is_member = False
            except Exception:
                is_member = False

            if not is_member:
                try:
                    await client(InviteToChannelRequest(chat_id, [new_owner]))
                    await reply_or_edit(event, f"📥 تم إضافة المستخدم {new_owner.first_name} للجروب تلقائياً")
                    await asyncio.sleep(2)
                except Exception as e:
                    await reply_or_edit(event,
                        f"❌ فشل إضافة المستخدم للجروب: {str(e)}\n"
                        f"⚠️ أضفه يدوياً ثم أعد المحاولة"
                    )
                    return

            await reply_or_edit(event,
                f"🔐 **نقل الملكية إلى:** {new_owner.first_name} (`{new_owner.id}`)\n\n"
                f"⚠️ هذا الإجراء لا يمكن التراجع عنه!\n"
                f"📲 أرسل كلمة سر التحقق بخطوتين (2FA) لتأكيد النقل:\n\n"
                f"أو أرسل `.الغاء` للإلغاء"
            )

            try:
                response = await client.wait_for(
                    events.NewMessage(from_users=owner_id, chats=event.chat_id),
                    timeout=120
                )
            except asyncio.TimeoutError:
                await event.respond("⏰ انتهت المهلة! تم إلغاء نقل الملكية")
                return

            password_text = response.raw_text.strip()
            try:
                await response.delete()
            except:
                pass

            if password_text == ".الغاء":
                await event.respond("🛑 تم إلغاء نقل الملكية")
                return

            try:
                from telethon.tl.functions.account import GetPasswordRequest, CheckPasswordRequest
                from telethon.password import compute_check
                pwd = await client(GetPasswordRequest())
                pwd_check = compute_check(pwd, password_text)
                await client(CheckPasswordRequest(password=pwd_check))
            except Exception as e:
                error_msg = str(e)
                if "PASSWORD_HASH_INVALID" in error_msg or "invalid" in error_msg.lower():
                    await event.respond("❌ كلمة السر غلط! تم إلغاء النقل")
                else:
                    await event.respond(f"❌ خطأ في التحقق: {error_msg}")
                return

            full_admin_rights = ChatAdminRights(
                change_info=True, post_messages=True, edit_messages=True,
                delete_messages=True, ban_users=True, invite_users=True,
                pin_messages=True, add_admins=True, anonymous=False,
                manage_call=True, other=True, manage_topics=True
            )

            try:
                await client(EditAdminRequest(
                    channel=chat_id, user_id=new_owner_id,
                    admin_rights=full_admin_rights, rank="مالك"
                ))
                try:
                    from telethon.tl.functions.channels import EditCreatorRequest
                    pwd = await client(GetPasswordRequest())
                    pwd_check = compute_check(pwd, password_text)
                    await client(EditCreatorRequest(
                        channel=chat_id, user_id=new_owner_id, password=pwd_check
                    ))
                    await event.respond(
                        f"✅ **تم نقل الملكية بنجاح!**\n\n"
                        f"👤 المالك الجديد: {new_owner.first_name}\n"
                        f"🆔 ID: `{new_owner.id}`"
                    )
                except Exception as e:
                    await event.respond(
                        f"⚠️ تم منح جميع صلاحيات الإدارة\n"
                        f"👤 المشرف: {new_owner.first_name}\n"
                        f"⚠️ نقل الملكية الكامل قد يتطلب إجراء يدوي\nالخطأ: {str(e)}"
                    )
            except ChatAdminRequiredError:
                await event.respond("❌ لازم تكون مالك الجروب/القناة!")
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)}")
        except Exception as e:
            await event.respond(f"❌ خطأ عام: {str(e)}")

    # ============================================================
    # ==================== نظام الـ INBOX ====================
    # ============================================================

    async def build_inbox_caption(sender, chat, message_text, source_type):
        sender_name = ""
        if sender:
            fname = getattr(sender, 'first_name', '') or ''
            lname = getattr(sender, 'last_name', '') or ''
            sender_name = f"{fname} {lname}".strip() or "مجهول"
        username = getattr(sender, 'username', None) if sender else None
        sender_id_val = getattr(sender, 'id', None) if sender else None
        chat_name = ""
        if chat and hasattr(chat, 'title') and chat.title:
            chat_name = chat.title
        icons = {"private": "💬 رسالة خاصة", "mention": "📢 منشن", "reply": "↩️ رد على رسالتك"}
        source_label = icons.get(source_type, "📩 رسالة")
        lines = [f"┌ {source_label}"]
        lines.append(f"├ 👤 من: **{sender_name}**")
        if username:
            lines.append(f"├ 🔗 يوزر: @{username}")
        if sender_id_val:
            lines.append(f"├ 🆔 ID: `{sender_id_val}`")
        if chat_name:
            lines.append(f"├ 🏠 الجروب: {chat_name}")
        if message_text and message_text.strip():
            preview = message_text[:200] + ("..." if len(message_text) > 200 else "")
            lines.append(f"├ 📝 الرسالة:\n│  {preview}")
        lines.append(f"└ 🕐 {datetime.now().strftime('%H:%M - %d/%m/%Y')}")
        return "\n".join(lines)

    async def get_inbox_button(sender):
        from telethon.tl.types import KeyboardButtonUrl
        from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
        sender_id_val = getattr(sender, 'id', None) if sender else None
        username = getattr(sender, 'username', None) if sender else None
        if not sender_id_val:
            return None
        url = f"https://t.me/{username}" if username else f"tg://user?id={sender_id_val}"
        fname = getattr(sender, 'first_name', '') or 'المستخدم'
        btn = KeyboardButtonUrl(text=f"💬 فتح محادثة مع {fname}", url=url)
        return ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[btn])])

    # مجموعة التخزين - يربطها المستخدم بأمر .تخزين
    target_chat_entity = None

    async def forward_to_inbox(event, source_type):
        try:
            if not target_chat_entity:
                logging.warning("⚠️ target_chat_entity مش موجود - الرسالة مش اتبعتت")
                return
            sender = await event.get_sender()
            chat   = await event.get_chat()
            text   = event.raw_text or ""
            caption  = await build_inbox_caption(sender, chat, text, source_type)
            reply_markup = await get_inbox_button(sender)
            if event.media:
                await client.send_file(
                    target_chat_entity, event.media,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='markdown'
                )
            else:
                await client.send_message(
                    target_chat_entity, caption,
                    reply_markup=reply_markup,
                    parse_mode='markdown'
                )
        except Exception as e:
            logging.error(f"❌ forward_to_inbox error: {e}")

    # ============================================================

    @client.on(events.NewMessage)
    async def handle_commands(event):
        nonlocal welcome_enabled, welcome_image_path, welcome_text_template, bot_enabled, keep_alive, target_chat_entity
        text = event.raw_text
        chat_id = event.chat_id
        sender_id = event.sender_id

        # ══════ INBOX: رسائل واردة (مش منك) ══════
        if not event.out:
            try:
                sender = await event.get_sender()
                is_bot_sender = sender and getattr(sender, 'bot', False)
                if not is_bot_sender and sender_id != owner_id:
                    if event.is_private:
                        await forward_to_inbox(event, "private")
                    elif event.is_group or event.is_channel:
                        is_mention = bool(event.mentioned)
                        is_reply_to_me = False
                        if event.is_reply:
                            try:
                                replied = await event.get_reply_message()
                                if replied and replied.sender_id == owner_id:
                                    is_reply_to_me = True
                            except Exception:
                                pass
                        if is_mention:
                            await forward_to_inbox(event, "mention")
                        elif is_reply_to_me:
                            await forward_to_inbox(event, "reply")
            except Exception as e:
                logging.error(f"❌ inbox handler error: {e}")

        # ════ أوامر التحكم في البوت (منك أنت فقط) ════
        if event.out:
            if text == ".تفعيل_البوت":
                bot_enabled = True
                await reply_or_edit(event, "✅ تم تفعيل البوت بنجاح!\n🟢 جميع الميزات تعمل الآن")
                return
            elif text == ".تعطيل_البوت":
                bot_enabled = False
                await reply_or_edit(event, "⏸️ تم تعطيل البوت مؤقتاً!\n🔴 جميع الميزات متوقفة\n💡 استخدم `.تفعيل_البوت` لإعادة التشغيل")
                return
            elif text == ".حالة_البوت":
                status = "🟢 مفعّل" if bot_enabled else "🔴 معطّل"
                uptime_status = "✅ تلقائي" if keep_alive else "❌ يدوي"
                await reply_or_edit(event,
                    f"📊 **حالة البوت:**\n\n"
                    f"⚡ الحالة: {status}\n"
                    f"🔄 إعادة الاتصال: {uptime_status}\n"
                    f"👤 الحساب: {me.first_name}\n"
                    f"📱 الهاتف: {user_data_store['phone']}"
                )
                return
            elif text == ".ايقاف":
                await reply_or_edit(event, "🛑 جاري إيقاف البوت...")
                await asyncio.sleep(1)
                keep_alive = False
                await client.disconnect()
                return

            # ════ أمر التخزين - ربط مجموعة الـ inbox ════
            elif text.startswith(".تخزين"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    await reply_or_edit(event,
                        "📦 **أمر التخزين**\n\n"
                        "الاستخدام:\n"
                        "`.تخزين <لينك أو ID المجموعة>`\n\n"
                        "مثال:\n"
                        "`.تخزين https://t.me/mygroup`\n"
                        "`.تخزين -1001234567890`\n\n"
                        f"الحالة الحالية: {'✅ مربوط بـ ' + target_chat_entity.title if target_chat_entity else '❌ غير مربوط'}"
                    )
                    return
                input_val = parts[1].strip()
                try:
                    await reply_or_edit(event, "⏳ جاري ربط المجموعة...")
                    entity = await client.get_entity(input_val)
                    target_chat_entity = entity
                    await reply_or_edit(event,
                        f"✅ **تم ربط مجموعة التخزين بنجاح!**\n\n"
                        f"📦 المجموعة: **{entity.title}**\n"
                        f"🆔 ID: `{entity.id}`\n\n"
                        f"الآن كل رسالة خاصة أو منشن أو رد هيتنسخ فيها تلقائياً 📥"
                    )
                except Exception as e:
                    await reply_or_edit(event,
                        f"❌ فشل ربط المجموعة!\n\n"
                        f"تأكد إنك:\n"
                        f"• عضو في المجموعة\n"
                        f"• اللينك أو الـ ID صح\n\n"
                        f"الخطأ: {str(e)}"
                    )
                return

            elif text == ".حالة_التخزين":
                if target_chat_entity:
                    await reply_or_edit(event,
                        f"📦 **مجموعة التخزين:**\n\n"
                        f"✅ مربوط بـ: **{target_chat_entity.title}**\n"
                        f"🆔 ID: `{target_chat_entity.id}`"
                    )
                else:
                    await reply_or_edit(event,
                        "❌ **مجموعة التخزين غير مربوطة**\n\n"
                        "استخدم: `.تخزين <لينك أو ID>`"
                    )
                return



        # ============ الترحيب التلقائي في الخاص فقط ============
        if event.is_private and not event.out and welcome_enabled:
            sender = await event.get_sender()
            if sender and not sender.bot and event.sender_id not in welcome_sent:
                welcome_sent.add(event.sender_id)
                wtext = welcome_text_template.format(link=OFFICIAL_CHANNEL_LINK)
                try:
                    if welcome_image_path and os.path.exists(welcome_image_path):
                        await client.send_file(
                            event.chat_id, welcome_image_path,
                            caption=wtext, link_preview=False, parse_mode='markdown'
                        )
                    else:
                        await event.respond(wtext, link_preview=False, parse_mode='markdown')
                except Exception as e:
                    logging.error(f"خطأ ترحيب: {e}")
                    try:
                        await event.respond(wtext, link_preview=False, parse_mode='markdown')
                    except:
                        pass

        # ============ التحقق من الفلاتر ============
        if text in filters_dict:
            await event.respond(filters_dict[text])

        # ============ معالجة الجروبات (حماية) ============
        if event.is_group and not event.out:
            sender_is_admin = await is_admin(event.chat_id, event.sender_id)

            if event.chat_id in muted_admins and event.sender_id in muted_admins[event.chat_id]:
                try:
                    await event.delete()
                except:
                    pass
                return

            if event.chat_id in muted_users and event.sender_id in muted_users[event.chat_id]:
                try:
                    await event.delete()
                except:
                    pass
                return

            if not sender_is_admin:
                if contains_banned_word(text, event.chat_id):
                    try:
                        await event.delete()
                    except:
                        pass
                    return

                if event.chat_id in links_locked and contains_link(text):
                    try:
                        await event.delete()
                    except:
                        pass
                    return

                if event.chat_id in locked_media:
                    locks = locked_media[event.chat_id]
                    should_delete = False
                    if 'صور' in locks and event.photo:
                        should_delete = True
                    elif 'فيديو' in locks and event.video:
                        should_delete = True
                    elif 'ملصقات' in locks and event.sticker:
                        should_delete = True
                    elif 'ملفات' in locks and event.document and not event.sticker and not event.video and not event.audio:
                        should_delete = True
                    elif 'صوت' in locks and (event.audio or event.voice):
                        should_delete = True
                    elif 'gif' in locks and event.gif:
                        should_delete = True
                    if should_delete:
                        try:
                            await event.delete()
                        except:
                            pass
                        return

        # ============ الرد العام ============
        if text.lower() in global_replies:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                await reply_msg.reply(global_replies[text.lower()])
            else:
                await event.reply(global_replies[text.lower()])
        elif text.lower() in global_replies_stickers:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                await client.send_file(event.chat_id, global_replies_stickers[text.lower()], reply_to=reply_msg.id)
            else:
                await client.send_file(event.chat_id, global_replies_stickers[text.lower()], reply_to=event.id)

        # ════ التحقق: هل الرسالة من صاحب الحساب ════
        if not event.out:
            return

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر المساعدة والمعلومات ═══════════════════
        # ════════════════════════════════════════════════════════════════

        if text == ".الاوامر":
            commands_list = f"""📌 **قائمة الأوامر الكاملة** 📌
══════════════════════

🔧 **أوامر التحكم في البوت:**
`.تفعيل_البوت` - تشغيل البوت
`.تعطيل_البوت` - إيقاف البوت مؤقتاً
`.حالة_البوت` - معرفة حالة البوت
`.ايقاف` - إيقاف البوت نهائياً
`.تخزين <لينك/ID>` - ربط مجموعة التخزين
`.حالة_التخزين` - عرض مجموعة التخزين الحالية

═════════════════════

🌐 **أوامر عامة:**
`.الاوامر` - عرض هذه القائمة
`.معلومات` - بيانات حسابك
`.حالة` - تحقق من حالة البوت
`.كشف` (رد) - معلومات المستخدم

═════════════════════

📢 **أوامر الإذاعة:**
`.اذاعة <رسالة>` - إرسال لكل المحادثات
`.اذاعة_خاص <رسالة>` - للمحادثات الخاصة فقط
`.اذاعة_جروب <رسالة>` - للمجموعات فقط
`.اذاعة_قناة <رسالة>` - للقنوات فقط
`.اذاعة_صورة` (رد على صورة) - إذاعة صورة
`.سبام <عدد> <رسالة>` - رسالة متكررة (حد أقصى 50)

══════════════════════

📊 **أوامر الإحصائيات:**
`.عدد_المحادثات` - إحصائيات شاملة
`.عدد_الرسائل @يوزر` - رسائل مستخدم معين
`.رسائلي` - عدد رسائلك في الشات

═══════════════════════

🗑️ **أوامر الحذف:**
`.حذف` (رد) - حذف رسالة معينة
`.حذفكل` - حذف آخر 100 رسالة
`.حذف_المجموعات` - مغادرة كل المجموعات
`.حذف_القنوات` - مغادرة كل القنوات
`.تنظيف_الخاص` - حذف رسائل المحادثة الخاصة
`.حذف_الفلاتر` - حذف جميع الفلاتر

═══════════════════════

💬 **أوامر متنوعة:**
`.ترجم <نص>` - ترجمة عربي/إنجليزي
`.صورتي` (رد على صورة) - تغيير صورة البروفايل
`.فلتر <كلمة> <رد>` - إضافة رد تلقائي
`.صوت <رابط>` - تحميل صوت من رابط
`.ارسال_ملف <رابط>` - تحميل ملف من رابط

═══════════════════════

🎉 **أوامر الترحيب (للخاص فقط):**
`.ترحيب تشغيل` - تفعيل الترحيب
`.ترحيب ايقاف` - إيقاف الترحيب
`.ترحيب حالة` - عرض حالة الترحيب
`.ترحيب_نص <النص>` - تغيير رسالة الترحيب
`.ترحيب_صورة` (رد) - إضافة صورة للترحيب
`.ترحيب_بدون_صورة` - إزالة صورة الترحيب

═══════════════════════

🔄 **أوامر الرد العام:**
`.رد_عام <كلمة> <الرد>` - إضافة رد نصي تلقائي
`.رد_عام_ملصق <كلمة>` (رد على ملصق) - رد بملصق
`.حذف_رد_عام <كلمة>` - حذف رد عام

══════════════════════

👥 **أوامر إدارة الأعضاء (جروبات):**
`.حظر` (رد/@يوزر/ID) - حظر عضو
`.فكحظر` (رد/@يوزر/ID) - فك حظر عضو
`.كتم` (رد/@يوزر/ID) - كتم + حذف جميع رسائله
`.فككتم` (رد/@يوزر/ID) - فك كتم
`.كتم_مشرف` (رد) - كتم مشرف وحذف رسائله
`.فك_كتم_مشرف` (رد) - فك كتم مشرف
`.طرد` (رد/@يوزر/ID) - طرد عضو
`.اضافة @يوزر` - إضافة عضو للجروب
`.تصفية` - حظر جميع الأعضاء (ماعدا المشرفين)

═══════════════════════

🔑 **أوامر الملكية:**
`.نقل_ملكية <ID أو @يوزر>` - نقل ملكية الجروب/القناة

═══════════════════════

🔒 **أوامر الحماية (جروبات):**
`.منع <كلمة>` - منع كلمة معينة
`.حذف_منع <كلمة>` - إزالة كلمة من القائمة
`.قائمة_المنع` - عرض الكلمات الممنوعة
`.قفل_روابط` - منع إرسال الروابط
`.فتح_روابط` - السماح بالروابط
`.قفل <صور/فيديو/ملصقات/ملفات/صوت/gif>`
`.فتح <صور/فيديو/ملصقات/ملفات/صوت/gif>`
`.قائمة_القفل` - عرض الميديا المقفولة

══════════════════════

⚙️ **أوامر إعدادات الجروب:**
`.وصف <نص>` - تغيير وصف الجروب
`.صورةمجموعة` (رد) - تغيير صورة الجروب
`.المشرفين` - قائمة المشرفين
`.رابط_الدعوة` - الحصول على رابط دعوة
`.منشن_الكل` - عمل منشن لجميع الأعضاء
`.فحص_الاعضاء` - إحصائيات الأعضاء
`.تصدير_الاعضاء` - تصدير قائمة الأعضاء
`.حالة_الجروب` - معلومات تفصيلية
`.انشاءمجموعات` - إنشاء 10 مجموعات تلقائياً

═══════════════════════

📢 **ملاحظات:**
- 🔄 البوت يعيد الاتصال تلقائياً إذا انقطع
- 🔇 أمر الكتم محسّن: يعمل بالرد/@يوزر/ID ويحذف جميع الرسائل
- ⚡ يمكنك تعطيل البوت مؤقتاً وإعادة تشغيله متى شئت
- 💡 جميع الأوامر محسّنة وتعمل بكفاءة

═══════════════════════
💡 القناة الرسمية: {OFFICIAL_CHANNEL_LINK}"""
            await reply_or_edit(event, commands_list)

        elif text == ".معلومات":
            try:
                me_info = await client.get_me()
                await reply_or_edit(event,
                    f"📋 **معلومات الحساب:**\n"
                    f"👤 الاسم: {me_info.first_name}\n"
                    f"🔖 المعرف: @{me_info.username or 'لا يوجد'}\n"
                    f"🆔 الـID: `{me_info.id}`\n"
                    f"📱 الهاتف: {me_info.phone or 'مخفي'}\n"
                    f"🤖 بوت: {'نعم' if me_info.bot else 'لا'}"
                )
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text == ".حالة":
            await reply_or_edit(event, "✅ البوت شغال بنجاح!")

        elif text == ".كشف" and event.is_reply:
            reply = await event.get_reply_message()
            try:
                user = await client.get_entity(reply.sender_id)
                await reply_or_edit(event,
                    f"📋 **معلومات المستخدم:**\n"
                    f"👤 الاسم: {user.first_name}\n"
                    f"🔖 المعرف: @{user.username or 'لا يوجد'}\n"
                    f"🆔 الـID: `{user.id}`\n"
                    f"📱 الهاتف: {user.phone or 'مخفي'}\n"
                    f"🤖 بوت: {'نعم' if user.bot else 'لا'}"
                )
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")
        elif text == ".كشف":
            await reply_or_edit(event, "⚠️ رد على رسالة للكشف عن معلومات المستخدم")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر الترحيب ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text == ".ترحيب تشغيل":
            welcome_enabled = True
            await reply_or_edit(event, "✅ تم تفعيل الترحيب التلقائي!")

        elif text == ".ترحيب ايقاف":
            welcome_enabled = False
            await reply_or_edit(event, "🛑 تم إيقاف الترحيب التلقائي!")

        elif text == ".ترحيب حالة":
            status = "✅ مفعّل" if welcome_enabled else "🛑 معطّل"
            img_status = "✅ موجودة" if (welcome_image_path and os.path.exists(welcome_image_path)) else "❌ بدون صورة"
            await reply_or_edit(event,
                f"📊 **حالة الترحيب:**\n"
                f"🔔 الحالة: {status}\n"
                f"🖼️ الصورة: {img_status}\n"
                f"📍 نطاق العمل: المحادثات الخاصة فقط\n"
                f"💡 يعمل: عند أول رسالة من مستخدم جديد"
            )

        elif text.startswith(".ترحيب_نص "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                welcome_text_template = args[1] + "\n[القناة الرسمية]({link})"
                await reply_or_edit(event, "✅ تم تحديث نص الترحيب بنجاح!")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.ترحيب_نص <النص الجديد>`")

        elif text == ".ترحيب_صورة" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.photo:
                try:
                    welcome_image_path = await client.download_media(reply.photo, file="welcome_photo.jpg")
                    await reply_or_edit(event, "✅ تم تعيين صورة الترحيب بنجاح!")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ في حفظ الصورة: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ رد على صورة لتعيينها كصورة ترحيب!")
        elif text == ".ترحيب_صورة":
            await reply_or_edit(event, "⚠️ رد على صورة لتعيينها كصورة ترحيب!")

        elif text == ".ترحيب_بدون_صورة":
            welcome_image_path = None
            await reply_or_edit(event, "✅ تم إزالة صورة الترحيب! الترحيب سيكون نصي فقط")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر الإذاعة ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text.startswith(".اذاعة ") and not text.startswith(".اذاعة_"):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    count = 0
                    await reply_or_edit(event, "📢 جاري الإذاعة لجميع المحادثات...")
                    async for dialog in client.iter_dialogs():
                        if dialog.entity.id != owner_id and not getattr(dialog.entity, 'bot', False):
                            try:
                                await client.send_message(dialog.entity, args[1])
                                count += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    await reply_or_edit(event, f"✅ تم إرسال الإذاعة إلى {count} محادثة!")
                except FloodWaitError as e:
                    await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة <الرسالة>`")

        elif text.startswith(".اذاعة_خاص "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    count = 0
                    await reply_or_edit(event, "📢 جاري الإذاعة للمحادثات الخاصة...")
                    async for dialog in client.iter_dialogs():
                        if dialog.is_user and dialog.entity.id != owner_id and not dialog.entity.bot:
                            try:
                                await client.send_message(dialog.entity, args[1])
                                count += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    await reply_or_edit(event, f"✅ تم إرسال الإذاعة إلى {count} محادثة خاصة!")
                except FloodWaitError as e:
                    await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة_خاص <الرسالة>`")

        elif text.startswith(".اذاعة_جروب "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    count = 0
                    await reply_or_edit(event, "📢 جاري الإذاعة للمجموعات...")
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group:
                            try:
                                await client.send_message(dialog.entity, args[1])
                                count += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    await reply_or_edit(event, f"✅ تم إرسال الإذاعة إلى {count} مجموعة!")
                except FloodWaitError as e:
                    await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة_جروب <الرسالة>`")

        elif text.startswith(".اذاعة_قناة "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    count = 0
                    await reply_or_edit(event, "📢 جاري الإذاعة للقنوات...")
                    async for dialog in client.iter_dialogs():
                        if dialog.is_channel and not dialog.is_group:
                            try:
                                await client.send_message(dialog.entity, args[1])
                                count += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    await reply_or_edit(event, f"✅ تم إرسال الإذاعة إلى {count} قناة!")
                except FloodWaitError as e:
                    await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة_قناة <الرسالة>`")

        elif text.startswith(".اذاعة_صورة") and event.is_reply:
            reply = await event.get_reply_message()
            args = text.split(maxsplit=1)
            caption = args[1] if len(args) > 1 else ""
            if reply.photo:
                try:
                    count = 0
                    await reply_or_edit(event, "📢 جاري إذاعة الصورة...")
                    photo = await client.download_media(reply.photo)
                    async for dialog in client.iter_dialogs():
                        if dialog.entity.id != owner_id and not getattr(dialog.entity, 'bot', False):
                            try:
                                await client.send_file(dialog.entity, photo, caption=caption)
                                count += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    await reply_or_edit(event, f"✅ تم إرسال الصورة إلى {count} محادثة!")
                    os.remove(photo)
                except FloodWaitError as e:
                    await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ رد على صورة لإذاعتها!")
        elif text.startswith(".اذاعة_صورة"):
            await reply_or_edit(event, "⚠️ رد على صورة لإذاعتها!")

        elif text.startswith(".سبام "):
            args = text.split(maxsplit=2)
            if len(args) > 2 and args[1].isdigit():
                count = min(int(args[1]), 50)
                try:
                    await reply_or_edit(event, f"⏳ جاري إرسال {count} رسالة...")
                    for _ in range(count):
                        await client.send_message(event.chat_id, args[2])
                        await asyncio.sleep(0.5)
                    await reply_or_edit(event, f"✅ تم إرسال {count} رسالة!")
                except FloodWaitError as e:
                    await event.respond(f"⚠️ فلود! انتظر {e.seconds} ثانية")
                except Exception as e:
                    await event.respond(f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.سبام <العدد> <الرسالة>`")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر الإحصائيات ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text == ".عدد_المحادثات":
            try:
                groups, channels, users = 0, 0, 0
                await reply_or_edit(event, "📊 جاري حساب المحادثات...")
                async for dialog in client.iter_dialogs():
                    if dialog.is_group:
                        groups += 1
                    elif dialog.is_channel:
                        channels += 1
                    elif dialog.is_user and not dialog.entity.bot:
                        users += 1
                total = groups + channels + users
                await reply_or_edit(event,
                    f"📊 **إحصائيات المحادثات:**\n\n"
                    f"📈 الإجمالي: {total}\n"
                    f"👥 المجموعات: {groups}\n"
                    f"📢 القنوات: {channels}\n"
                    f"💬 المحادثات الخاصة: {users}"
                )
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text.startswith(".عدد_الرسائل "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    user = await client.get_entity(args[1].strip('@'))
                    count = 0
                    await reply_or_edit(event, "📊 جاري الحساب...")
                    async for msg in client.iter_messages(event.chat_id, from_user=user):
                        count += 1
                    await reply_or_edit(event, 
                        f"📬 **إحصائيات الرسائل:**\n\n"
                        f"👤 المستخدم: @{user.username or user.first_name}\n"
                        f"💬 عدد الرسائل: {count}"
                    )
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.عدد_الرسائل @username`")

        elif text == ".رسائلي":
            try:
                count = 0
                await reply_or_edit(event, "📊 جاري حساب رسائلك...")
                async for msg in client.iter_messages(event.chat_id, from_user='me'):
                    count += 1
                await reply_or_edit(event, f"📬 عدد رسائلك في هذا الشات: **{count}** رسالة")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر الحذف والمغادرة ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text == ".حذف" and event.is_reply:
            reply = await event.get_reply_message()
            try:
                await client.delete_messages(event.chat_id, [reply.id, event.id])
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ في الحذف: {str(e)}")
        elif text == ".حذف":
            await reply_or_edit(event, "⚠️ رد على رسالة لحذفها")

        elif text == ".حذفكل":
            try:
                messages = await client.get_messages(event.chat_id, limit=100)
                await client.delete_messages(event.chat_id, [msg.id for msg in messages])
                await event.respond("✅ تم حذف آخر 100 رسالة!")
            except ChatAdminRequiredError:
                await reply_or_edit(event, "❌ يجب أن تكون مشرفاً!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text == ".حذف_المجموعات":
            try:
                count = 0
                await reply_or_edit(event, "🔄 جاري مغادرة المجموعات...")
                async for dialog in client.iter_dialogs():
                    if dialog.is_group:
                        try:
                            if not dialog.entity.admin_rights and not dialog.entity.creator:
                                await client(LeaveChannelRequest(dialog.entity.id))
                                count += 1
                                await asyncio.sleep(1)
                        except:
                            pass
                await reply_or_edit(event, f"✅ تم مغادرة {count} مجموعة!")
            except FloodWaitError as e:
                await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text == ".حذف_القنوات":
            try:
                count = 0
                await reply_or_edit(event, "🔄 جاري مغادرة القنوات...")
                async for dialog in client.iter_dialogs():
                    if dialog.is_channel and not dialog.is_group:
                        try:
                            if not dialog.entity.admin_rights and not dialog.entity.creator:
                                await client(LeaveChannelRequest(dialog.entity.id))
                                count += 1
                                await asyncio.sleep(1)
                        except:
                            pass
                await reply_or_edit(event, f"✅ تم مغادرة {count} قناة!")
            except FloodWaitError as e:
                await reply_or_edit(event, f"⚠️ فلود! انتظر {e.seconds} ثانية")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text == ".تنظيف_الخاص" and event.is_private:
            try:
                messages = await client.get_messages(event.chat_id, limit=1000)
                await client.delete_messages(event.chat_id, [msg.id for msg in messages])
                await event.respond("✅ تم تنظيف المحادثة الخاصة!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {str(e)}")

        elif text == ".حذف_الفلاتر":
            filters_dict.clear()
            await reply_or_edit(event, "✅ تم حذف جميع الفلاتر!")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر متنوعة ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text.startswith(".ترجم "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    if any('\u0600' <= c <= '\u06FF' for c in args[1]):
                        translator = GoogleTranslator(source='ar', target='en')
                    else:
                        translator = GoogleTranslator(source='auto', target='ar')
                    translated = translator.translate(args[1])
                    await reply_or_edit(event, f"📖 **الترجمة:**\n\n{translated}")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ في الترجمة: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.ترجم <النص>`")

        elif text == ".صورتي" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.photo:
                try:
                    photo = await client.download_media(reply.photo)
                    file = await client.upload_file(photo)
                    from telethon.tl.functions.photos import UploadProfilePhotoRequest
                    await client(UploadProfilePhotoRequest(file))
                    await reply_or_edit(event, "✅ تم تغيير صورة البروفايل بنجاح!")
                    os.remove(photo)
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ رد على صورة!")
        elif text == ".صورتي":
            await reply_or_edit(event, "⚠️ رد على صورة لتعيينها كصورة بروفايل!")

        elif text.startswith(".فلتر "):
            args = text.split(maxsplit=2)
            if len(args) > 2:
                filters_dict[args[1]] = args[2]
                await reply_or_edit(event, f"✅ تم إضافة فلتر:\n**الكلمة:** {args[1]}\n**الرد:** {args[2]}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.فلتر <الكلمة> <الرد>`")

        elif text.startswith(".صوت "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    await reply_or_edit(event, "⏳ جاري تحميل الصوت...")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(args[1]) as resp:
                            if resp.status == 200:
                                audio = await resp.read()
                                await client.send_file(event.chat_id, audio, voice_note=True)
                                try:
                                    await event.delete()
                                except:
                                    pass
                            else:
                                await reply_or_edit(event, "⚠️ الرابط غير صالح!")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ في التحميل: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.صوت <الرابط>`")

        elif text.startswith(".ارسال_ملف "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                try:
                    await reply_or_edit(event, "⏳ جاري تحميل الملف...")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(args[1]) as resp:
                            if resp.status == 200:
                                file = await resp.read()
                                await client.send_file(event.chat_id, file)
                                await reply_or_edit(event, "✅ تم إرسال الملف!")
                            else:
                                await reply_or_edit(event, "⚠️ الرابط غير صالح!")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.ارسال_ملف <الرابط>`")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر الرد العام ═══════════════════
        # ════════════════════════════════════════════════════════════════

        elif text.startswith(".رد_عام ") and not text.startswith(".رد_عام_ملصق"):
            args = text.split(maxsplit=2)
            if len(args) > 2:
                global_replies[args[1].lower()] = args[2]
                await reply_or_edit(event, f"✅ تم إضافة رد عام:\n**الكلمة:** {args[1]}\n**الرد:** {args[2]}")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.رد_عام <الكلمة> <الرد>`")

        elif text.startswith(".رد_عام_ملصق ") and event.is_reply:
            args = text.split(maxsplit=1)
            if len(args) > 1:
                reply = await event.get_reply_message()
                if reply.sticker:
                    global_replies_stickers[args[1].lower()] = reply.sticker
                    await reply_or_edit(event, f"✅ تم إضافة رد عام بملصق للكلمة: **{args[1]}**")
                else:
                    await reply_or_edit(event, "⚠️ رد على ملصق!")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.رد_عام_ملصق <الكلمة>` (مع الرد على ملصق)")
        elif text.startswith(".رد_عام_ملصق"):
            await reply_or_edit(event, "⚠️ رد على ملصق واكتب `.رد_عام_ملصق <الكلمة>`")

        elif text.startswith(".حذف_رد_عام "):
            args = text.split(maxsplit=1)
            if len(args) > 1:
                key = args[1].lower()
                if key in global_replies:
                    del global_replies[key]
                    await reply_or_edit(event, f"✅ تم حذف الرد العام: **{args[1]}**")
                elif key in global_replies_stickers:
                    del global_replies_stickers[key]
                    await reply_or_edit(event, f"✅ تم حذف الرد العام (ملصق): **{args[1]}**")
                else:
                    await reply_or_edit(event, "⚠️ الكلمة غير موجودة في الردود العامة!")
            else:
                await reply_or_edit(event, "⚠️ الاستخدام: `.حذف_رد_عام <الكلمة>`")

        # ════════════════════════════════════════════════════════════════
        # ═══════════════════ أوامر إدارة الجروبات ═══════════════════
        # ════════════════════════════════════════════════════════════════

        # تحقق من أن الأمر في جروب فقط
        if event.is_group:

            if text.startswith(".كتم") and not text.startswith(".كتم_مشرف"):
                target_id = None
                target_entity = None
                args = text.split()
                
                if event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    try:
                        target_entity = await client.get_entity(target_id)
                    except:
                        target_entity = None
                elif len(args) > 1:
                    target_id, target_entity = await get_user_from_input(args[1], event.chat_id)
                    if not target_id:
                        await reply_or_edit(event, "❌ خطأ في جلب المستخدم!\n💡 تأكد أن المستخدم موجود في المجموعة")
                        return
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.كتم` (رد) أو `.كتم @username` أو `.كتم <ID>`")
                    return
                
                if target_id:
                    try:
                        await client.edit_permissions(event.chat_id, target_id, send_messages=False)
                        
                        if event.chat_id not in muted_users:
                            muted_users[event.chat_id] = set()
                        muted_users[event.chat_id].add(target_id)
                        
                        deleted_count = 0
                        status_msg = await event.respond("🔄 جاري حذف رسائل المستخدم...")
                        
                        async for msg in client.iter_messages(event.chat_id, from_user=target_id):
                            try:
                                await msg.delete()
                                deleted_count += 1
                                
                                if deleted_count % 50 == 0:
                                    try:
                                        await status_msg.edit(f"🔄 تم حذف {deleted_count} رسالة...")
                                    except:
                                        pass
                                        
                                await asyncio.sleep(0.1)
                            except:
                                pass
                        
                        try:
                            await status_msg.delete()
                        except:
                            pass
                        
                        user_name = target_entity.first_name if target_entity else f"ID: {target_id}"
                        await reply_or_edit(event, f"🔇 **تم كتم {user_name} بنجاح!**\n📊 تم حذف {deleted_count} رسالة")
                        
                    except ChatAdminRequiredError:
                        await reply_or_edit(event, "❌ يجب أن تكون مشرفاً مع صلاحية كتم الأعضاء!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text.startswith(".فككتم"):
                target_id = None
                target_entity = None
                args = text.split()
                
                if event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    try:
                        target_entity = await client.get_entity(target_id)
                    except:
                        target_entity = None
                elif len(args) > 1:
                    target_id, target_entity = await get_user_from_input(args[1], event.chat_id)
                    if not target_id:
                        await reply_or_edit(event, "❌ خطأ في جلب المستخدم!")
                        return
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.فككتم` (رد) أو `.فككتم @username` أو `.فككتم <ID>`")
                    return
                
                if target_id:
                    try:
                        await client.edit_permissions(event.chat_id, target_id, send_messages=True)
                        
                        if event.chat_id in muted_users and target_id in muted_users[event.chat_id]:
                            muted_users[event.chat_id].discard(target_id)
                        
                        user_name = target_entity.first_name if target_entity else f"ID: {target_id}"
                        await reply_or_edit(event, f"🔊 تم فك كتم {user_name} بنجاح!")
                    except ChatAdminRequiredError:
                        await reply_or_edit(event, "❌ يجب أن تكون مشرفاً!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".تصفية":
                try:
                    status_msg = await event.respond("🔄 جاري تصفية جميع الأعضاء...\n⏳ قد يستغرق وقتاً حسب عدد الأعضاء")
                    total = 0
                    banned = 0
                    failed = 0
                    skipped_admins = 0

                    async for user in client.iter_participants(event.chat_id):
                        if user.id == owner_id or user.bot:
                            continue

                        user_is_admin = await is_admin(event.chat_id, user.id)
                        if user_is_admin:
                            skipped_admins += 1
                            continue

                        total += 1
                        try:
                            await client.edit_permissions(event.chat_id, user.id, view_messages=False)
                            banned += 1
                            await asyncio.sleep(0.5)

                            if banned % 20 == 0:
                                try:
                                    await status_msg.edit(
                                        f"🔄 جاري التصفية...\n\n"
                                        f"✅ تم حظر: {banned}\n"
                                        f"❌ فشل: {failed}\n"
                                        f"👮 مشرفين تم تخطيهم: {skipped_admins}"
                                    )
                                except:
                                    pass
                        except FloodWaitError as e:
                            logging.warning(f"فلود انتظار {e.seconds} ثانية")
                            await asyncio.sleep(e.seconds)
                            try:
                                await client.edit_permissions(event.chat_id, user.id, view_messages=False)
                                banned += 1
                            except:
                                failed += 1
                        except Exception as e:
                            failed += 1
                            logging.error(f"خطأ حظر {user.id}: {str(e)}")

                    try:
                        await status_msg.edit(
                            f"✅ **تمت التصفية بنجاح!**\n\n"
                            f"📊 **الإحصائيات:**\n"
                            f"👥 إجمالي الأعضاء: {total}\n"
                            f"✅ تم حظرهم: {banned}\n"
                            f"❌ فشل: {failed}\n"
                            f"👮 مشرفين تم تخطيهم: {skipped_admins}"
                        )
                    except:
                        await event.respond(f"✅ تصفية: حظر {banned} | فشل {failed} | مشرفين {skipped_admins}")

                except ChatAdminRequiredError:
                    await reply_or_edit(event, "❌ يجب أن تكون مشرفاً مع صلاحية حظر الأعضاء!")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text.startswith(".نقل_ملكية"):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    target = args[1].strip()
                    try:
                        if target.isdigit():
                            new_owner_id = int(target)
                        elif target.startswith('@'):
                            entity = await client.get_entity(target)
                            new_owner_id = entity.id
                        else:
                            try:
                                new_owner_id = int(target)
                            except ValueError:
                                entity = await client.get_entity(target)
                                new_owner_id = entity.id
                        await transfer_ownership(event.chat_id, new_owner_id, event)
                    except ValueError:
                        await reply_or_edit(event, "❌ ID غير صالح!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")
                else:
                    await reply_or_edit(event,
                        "⚠️ **الاستخدام:**\n"
                        "`.نقل_ملكية <ID>` أو `.نقل_ملكية @username`"
                    )

            elif text.startswith(".حظر"):
                args = text.split()
                target_id = None
                target_entity = None
                
                if len(args) > 1:
                    target_id, target_entity = await get_user_from_input(args[1], event.chat_id)
                    if not target_id:
                        await reply_or_edit(event, "❌ خطأ في جلب المستخدم!\n💡 تأكد أن المستخدم موجود في المجموعة")
                        return
                elif event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    try:
                        target_entity = await client.get_entity(target_id)
                    except:
                        target_entity = None
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.حظر @username` أو `.حظر <ID>` أو رد على رسالة")
                    return
                    
                if target_id:
                    try:
                        await client.edit_permissions(event.chat_id, target_id, view_messages=False)
                        user_name = target_entity.first_name if target_entity else f"ID: {target_id}"
                        await reply_or_edit(event, f"🚫 تم حظر {user_name} بنجاح!")
                    except ChatAdminRequiredError:
                        await reply_or_edit(event, "❌ يجب أن تكون مشرفاً!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text.startswith(".فكحظر"):
                args = text.split()
                target_id = None
                target_entity = None
                
                if len(args) > 1:
                    target_id, target_entity = await get_user_from_input(args[1], event.chat_id)
                    if not target_id:
                        await reply_or_edit(event, "❌ خطأ في جلب المستخدم!")
                        return
                elif event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    try:
                        target_entity = await client.get_entity(target_id)
                    except:
                        target_entity = None
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.فكحظر @username` أو `.فكحظر <ID>` أو رد على رسالة")
                    return
                    
                if target_id:
                    try:
                        await client.edit_permissions(event.chat_id, target_id, view_messages=True)
                        user_name = target_entity.first_name if target_entity else f"ID: {target_id}"
                        await reply_or_edit(event, f"✅ تم فك حظر {user_name}!")
                    except ChatAdminRequiredError:
                        await reply_or_edit(event, "❌ يجب أن تكون مشرفاً!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text.startswith(".كتم_مشرف"):
                if event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    if event.chat_id not in muted_admins:
                        muted_admins[event.chat_id] = set()
                    muted_admins[event.chat_id].add(target_id)
                    await reply_or_edit(event, "🔇 تم كتم المشرف! (سيتم حذف رسائله تلقائياً)")
                else:
                    await reply_or_edit(event, "⚠️ رد على رسالة المشرف لكتمه")

            elif text.startswith(".فك_كتم_مشرف"):
                if event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    if event.chat_id in muted_admins and target_id in muted_admins[event.chat_id]:
                        muted_admins[event.chat_id].discard(target_id)
                        await reply_or_edit(event, "🔊 تم فك كتم المشرف!")
                    else:
                        await reply_or_edit(event, "⚠️ هذا المشرف غير مكتوم أصلاً!")
                else:
                    await reply_or_edit(event, "⚠️ رد على رسالة المشرف لفك كتمه")

            elif text.startswith(".طرد"):
                args = text.split()
                target_id = None
                target_entity = None
                
                if len(args) > 1:
                    target_id, target_entity = await get_user_from_input(args[1], event.chat_id)
                    if not target_id:
                        await reply_or_edit(event, "❌ خطأ في جلب المستخدم!")
                        return
                elif event.is_reply:
                    reply = await event.get_reply_message()
                    target_id = reply.sender_id
                    try:
                        target_entity = await client.get_entity(target_id)
                    except:
                        target_entity = None
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.طرد @username` أو `.طرد <ID>` أو رد على رسالة")
                    return
                    
                if target_id:
                    try:
                        await client.edit_permissions(event.chat_id, target_id, view_messages=False)
                        await asyncio.sleep(1)
                        await client.edit_permissions(event.chat_id, target_id, view_messages=True)
                        
                        user_name = target_entity.first_name if target_entity else f"ID: {target_id}"
                        await reply_or_edit(event, f"👋 تم طرد {user_name}!")
                    except ChatAdminRequiredError:
                        await reply_or_edit(event, "❌ يجب أن تكون مشرفاً!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text.startswith(".اضافة "):
                args = text.split()
                if len(args) > 1:
                    try:
                        user = await client.get_entity(args[1].strip('@'))
                        await client(InviteToChannelRequest(event.chat_id, [user]))
                        await reply_or_edit(event, f"✅ تم إضافة {user.first_name} للمجموعة!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.اضافة @username`")

            elif text.startswith(".منع "):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    word = args[1].lower()
                    if event.chat_id not in custom_banned_words:
                        custom_banned_words[event.chat_id] = set()
                    custom_banned_words[event.chat_id].add(word)
                    await reply_or_edit(event, f"✅ تم منع الكلمة: **{word}**")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.منع <الكلمة>`")

            elif text.startswith(".حذف_منع "):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    word = args[1].lower()
                    if event.chat_id in custom_banned_words and word in custom_banned_words[event.chat_id]:
                        custom_banned_words[event.chat_id].remove(word)
                        await reply_or_edit(event, f"✅ تم إزالة الكلمة: **{word}**")
                    else:
                        await reply_or_edit(event, "⚠️ الكلمة غير موجودة في القائمة!")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.حذف_منع <الكلمة>`")

            elif text == ".قائمة_المنع":
                if event.chat_id in custom_banned_words and custom_banned_words[event.chat_id]:
                    words = "\n".join([f"• {word}" for word in custom_banned_words[event.chat_id]])
                    await reply_or_edit(event, f"📋 **الكلمات الممنوعة:**\n\n{words}")
                else:
                    await reply_or_edit(event, "⚠️ لا توجد كلمات ممنوعة في هذه المجموعة")

            elif text == ".قفل_روابط":
                links_locked.add(event.chat_id)
                await reply_or_edit(event, "🔒 تم قفل الروابط! سيتم حذف أي رسالة تحتوي على روابط")

            elif text == ".فتح_روابط":
                if event.chat_id in links_locked:
                    links_locked.remove(event.chat_id)
                await reply_or_edit(event, "🔓 تم فتح الروابط!")

            elif text.startswith(".قفل "):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    media_type = args[1]
                    if event.chat_id not in locked_media:
                        locked_media[event.chat_id] = set()
                    locked_media[event.chat_id].add(media_type)
                    await reply_or_edit(event, f"🔒 تم قفل: **{media_type}**")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.قفل <صور/فيديو/ملصقات/ملفات/صوت/gif>`")

            elif text.startswith(".فتح "):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    media_type = args[1]
                    if event.chat_id in locked_media and media_type in locked_media[event.chat_id]:
                        locked_media[event.chat_id].remove(media_type)
                        await reply_or_edit(event, f"🔓 تم فتح: **{media_type}**")
                    else:
                        await reply_or_edit(event, f"⚠️ **{media_type}** غير مقفول!")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.فتح <صور/فيديو/ملصقات/ملفات/صوت/gif>`")

            elif text == ".قائمة_القفل":
                if event.chat_id in locked_media and locked_media[event.chat_id]:
                    items = "\n".join([f"• {item}" for item in locked_media[event.chat_id]])
                    await reply_or_edit(event, f"🔒 **الميديا المقفولة:**\n\n{items}")
                else:
                    await reply_or_edit(event, "⚠️ لا يوجد ميديا مقفول في هذه المجموعة")

            elif text.startswith(".وصف "):
                args = text.split(maxsplit=1)
                if len(args) > 1:
                    try:
                        from telethon.tl.functions.messages import EditChatAboutRequest
                        await client(EditChatAboutRequest(event.chat_id, args[1]))
                        await reply_or_edit(event, "✅ تم تغيير وصف المجموعة!")
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")
                else:
                    await reply_or_edit(event, "⚠️ الاستخدام: `.وصف <النص>`")

            elif text == ".صورةمجموعة" and event.is_reply:
                reply = await event.get_reply_message()
                if reply.photo:
                    try:
                        photo = await client.download_media(reply.photo)
                        file = await client.upload_file(photo)
                        await client(EditPhotoRequest(
                            channel=event.chat_id,
                            photo=InputChatUploadedPhoto(file)
                        ))
                        await reply_or_edit(event, "✅ تم تغيير صورة المجموعة!")
                        os.remove(photo)
                    except Exception as e:
                        await reply_or_edit(event, f"❌ خطأ: {str(e)}")
                else:
                    await reply_or_edit(event, "⚠️ رد على صورة!")

            elif text == ".المشرفين":
                try:
                    admins = await client.get_participants(event.chat_id, filter=ChannelParticipantsAdmins)
                    admin_list = "\n".join([
                        f"• {admin.first_name} (@{admin.username or 'لا يوجد'})"
                        for admin in admins
                    ])
                    await reply_or_edit(event, f"👮 **المشرفين ({len(admins)}):**\n\n{admin_list}")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".رابط_الدعوة":
                try:
                    invite = await client(ExportChatInviteRequest(event.chat_id))
                    await reply_or_edit(event, f"🔗 **رابط الدعوة:**\n{invite.link}")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".منشن_الكل":
                try:
                    mentions = []
                    count = 0
                    async for user in client.iter_participants(event.chat_id):
                        if not user.bot and count < 50:
                            mentions.append(f"[{user.first_name}](tg://user?id={user.id})")
                            count += 1
                    
                    mention_text = " ".join(mentions)
                    await event.respond(f"📢 **منشن الكل:**\n\n{mention_text}")
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".فحص_الاعضاء":
                try:
                    total = 0
                    bots = 0
                    deleted = 0
                    
                    async for user in client.iter_participants(event.chat_id):
                        total += 1
                        if user.bot:
                            bots += 1
                        if user.deleted:
                            deleted += 1
                    
                    await reply_or_edit(event,
                        f"📊 **إحصائيات الأعضاء:**\n\n"
                        f"👥 الإجمالي: {total}\n"
                        f"🤖 البوتات: {bots}\n"
                        f"👻 الحسابات المحذوفة: {deleted}\n"
                        f"🧑 الأعضاء الفعليين: {total - bots - deleted}"
                    )
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".تصدير_الاعضاء":
                try:
                    members = []
                    async for user in client.iter_participants(event.chat_id):
                        members.append({
                            'id': user.id,
                            'name': user.first_name,
                            'username': user.username or 'لا يوجد',
                            'bot': user.bot
                        })
                    
                    filename = f"members_{event.chat_id}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(members, f, ensure_ascii=False, indent=2)
                    
                    await client.send_file(event.chat_id, filename, caption=f"📋 قائمة الأعضاء ({len(members)} عضو)")
                    os.remove(filename)
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".حالة_الجروب":
                try:
                    chat = await client.get_entity(event.chat_id)
                    admins = await client.get_participants(event.chat_id, filter=ChannelParticipantsAdmins)
                    
                    await reply_or_edit(event,
                        f"📊 **معلومات المجموعة:**\n\n"
                        f"📌 الاسم: {chat.title}\n"
                        f"🆔 الـID: `{chat.id}`\n"
                        f"👥 الأعضاء: {chat.participants_count or 'غير محدد'}\n"
                        f"👮 المشرفين: {len(admins)}\n"
                        f"📝 الوصف: {getattr(chat, 'about', 'لا يوجد')}"
                    )
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

            elif text == ".انشاءمجموعات":
                try:
                    created = 0
                    failed = 0
                    status_msg = await event.respond("🔄 جاري إنشاء المجموعات...")
                    
                    for i in range(1, 11):
                        try:
                            result = await client(CreateChannelRequest(
                                title=f"مجموعة {i}",
                                about=f"تم الإنشاء تلقائياً - {datetime.now().strftime('%Y-%m-%d')}",
                                megagroup=True
                            ))
                            created += 1
                            await asyncio.sleep(2)
                            
                            if created % 3 == 0:
                                try:
                                    await status_msg.edit(f"🔄 تم إنشاء {created} مجموعة...")
                                except:
                                    pass
                        except FloodWaitError as e:
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            failed += 1
                            logging.error(f"خطأ في إنشاء مجموعة: {str(e)}")
                    
                    await status_msg.edit(
                        f"✅ **اكتمل الإنشاء!**\n\n"
                        f"✅ تم إنشاء: {created} مجموعة\n"
                        f"❌ فشل: {failed} مجموعة"
                    )
                except Exception as e:
                    await reply_or_edit(event, f"❌ خطأ: {str(e)}")

    print("⚡ البوت جاهز ويعمل بكامل الميزات!")
    
    # حلقة إعادة الاتصال التلقائي - بدون run_until_disconnected لتجنب تعارض asyncio.shield في Python 3.13
    while keep_alive:
        try:
            if not client.is_connected():
                print("🔄 إعادة الاتصال خلال 5 ثواني...")
                await asyncio.sleep(5)
                try:
                    await client.connect()
                    if await client.is_user_authorized():
                        print("✅ تم إعادة الاتصال بنجاح!")
                    else:
                        logging.error("❌ الجلسة غير مصرح بها بعد إعادة الاتصال")
                        break
                except Exception as reconnect_error:
                    logging.error(f"فشل إعادة الاتصال: {str(reconnect_error)}")
                    await asyncio.sleep(10)
            else:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"خطأ في حلقة الاتصال: {str(e)}")
            await asyncio.sleep(10)
    
    print("🛑 تم إيقاف البوت")