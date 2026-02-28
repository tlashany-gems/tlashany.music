import os
import asyncio
import logging
import re
from telethon import events, TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError
from telethon.tl.functions.channels import (
    EditAdminRequest, InviteToChannelRequest, GetParticipantRequest
)
from telethon.tl.types import (
    ChannelParticipantsAdmins, ChatAdminRights
)
from telethon.errors.rpcerrorlist import UserNotParticipantError, UserIdInvalidError

logging.basicConfig(
    filename='userbot_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ══════════════════════════════════════════
#              الثوابت الثابتة
# ══════════════════════════════════════════
OFFICIAL_CHANNEL_LINK = "https://t.me/I0_I6"
WELCOME_GIF = "https://i.postimg.cc/wxV3PspQ/1756574872401.gif"

SOURCE_TAG = """
╭━─━─━Source━─━─━➾
        @I0_I6
╰━─━─━Source━─━─━➾"""

COMMANDS_TEXT = """📌 **قائمة الأوامر** 📌
━━━━━━━━━━━━━━━━━━━━

🛡️ **الحماية (جروبات):**
`.حظر` — حظر عضو (رد / يوزر / ID)
`.فكحظر` — فك حظر عضو
`.كتم` — تقييد العضو من الإرسال + حذف رسائله
`.فككتم` — فك التقييد
`.كتم_مشرف` — حذف رسائل مشرف تلقائياً
`.فك_كتم_مشرف` — إيقاف حذف رسائل المشرف

━━━━━━━━━━━━━━━━━━━━

📢 **الإذاعة:**
`.اذاعة_خاص <رسالة>` — إرسال لكل المحادثات الخاصة
`.اذاعة_جروب <رسالة>` — إرسال لكل المجموعات

━━━━━━━━━━━━━━━━━━━━

📡 **متابعة القناة (كروت الشحن):**
`.تتبع_قناة <@قناة_المصدر> <@قناة_الاستلام>` — بدء التتبع
`.وقف_التتبع` — إيقاف التتبع

━━━━━━━━━━━━━━━━━━━━

👋 **الترحيب (خاص):**
يتفعل تلقائياً عند أول رسالة
`.قبول` (رد على رسالة) — إيقاف الترحيب لهذا المستخدم

━━━━━━━━━━━━━━━━━━━━
"""

# ══════════════════════════════════════════
#              الدالة الرئيسية
# ══════════════════════════════════════════
async def start_userbot(client: TelegramClient, target_chat, user_data_store):
    me = await client.get_me()
    owner_id = me.id
    logging.info(f"✅ يوزربوت شغال: {me.first_name} ({owner_id})")
    print(f"✅ يوزربوت شغال: {me.first_name} ({owner_id})")

    # ══ الحالات الداخلية ══
    muted_admins = {}          # {chat_id: set(user_ids)}
    welcomed_users = set()     # المستخدمين اللي اتبعتلهم ترحيب
    accepted_users = set()     # المستخدمين اللي اتعملهم .قبول
    tracked_channels = {}      # {source_channel_id: dest_channel_id}

    # ══════════════════════════════════════════
    #         وظائف مساعدة مشتركة
    # ══════════════════════════════════════════
    async def reply_or_edit(event, text, **kwargs):
        try:
            if event.out:
                await event.edit(text, **kwargs)
            else:
                await event.respond(text, **kwargs)
        except Exception:
            try:
                await event.respond(text, **kwargs)
            except Exception as e:
                logging.error(f"فشل الرد: {e}")

    async def resolve_target(event, args):
        """
        يرجع user_id من:
        - رد على رسالة
        - يوزرنيم (@someone)
        - ID رقمي
        """
        if event.is_reply:
            reply = await event.get_reply_message()
            return reply.sender_id
        if args:
            target = args[0].strip()
            try:
                entity = await client.get_entity(target.lstrip('@') if target.startswith('@') else int(target))
                return entity.id
            except Exception as e:
                await reply_or_edit(event, f"❌ مش قادر أجيب المستخدم: {e}")
                return None
        await reply_or_edit(event, "⚠️ استخدم: رد على رسالة أو اكتب @يوزر أو ID")
        return None

    async def is_admin(chat_id, user_id):
        try:
            admins = await client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            return any(a.id == user_id for a in admins)
        except Exception:
            return False

    # ══════════════════════════════════════════
    #         متابعة القنوات (كروت الشحن)
    # ══════════════════════════════════════════
    @client.on(events.NewMessage)
    async def monitor_channels(event):
        """يراقب القنوات المحددة ويستخرج أرقام الكروت"""
        if not tracked_channels:
            return
        chat_id = event.chat_id
        if chat_id not in tracked_channels:
            return

        text = event.raw_text or ""
        # استخراج أرقام الكروت بصيغة *858*XXXXXXXXXXXXXXX#
        cards = re.findall(r'\*858\*(\d+)#', text)
        if not cards:
            return

        dest_channel = tracked_channels[chat_id]
        for card_number in cards:
            card_msg = f"*858*{card_number}#"
            try:
                await client.send_message(dest_channel, card_msg)
                logging.info(f"✅ أُرسل كرت: {card_msg} → {dest_channel}")
            except Exception as e:
                logging.error(f"❌ فشل إرسال الكرت: {e}")

    # ══════════════════════════════════════════
    #         الترحيب التلقائي في الخاص
    # ══════════════════════════════════════════
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def auto_welcome(event):
        sender_id = event.sender_id
        if sender_id in welcomed_users or sender_id in accepted_users:
            return
        sender = await event.get_sender()
        if not sender or getattr(sender, 'bot', False):
            return

        welcomed_users.add(sender_id)
        welcome_text = (
            f"أهلاً وسهلاً بيك! 🔥\n\n"
            f"سيب رسالتك وهنرد عليك في أقرب وقت 💬\n\n"
            f"{SOURCE_TAG}"
        )
        try:
            await client.send_file(
                event.chat_id,
                WELCOME_GIF,
                caption=welcome_text,
                parse_mode='markdown'
            )
        except Exception:
            try:
                await event.respond(welcome_text, parse_mode='markdown')
            except Exception as e:
                logging.error(f"❌ خطأ ترحيب: {e}")

    # ══════════════════════════════════════════
    #              معالج الأوامر
    # ══════════════════════════════════════════
    @client.on(events.NewMessage(outgoing=True))
    async def handle_commands(event):
        text = event.raw_text.strip()
        if not text:
            return

        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # ════ قائمة الأوامر ════
        if cmd in (".الاوامر", ".اوامري"):
            await reply_or_edit(event, COMMANDS_TEXT, parse_mode='markdown')
            return

        # ════ قبول (إيقاف ترحيب لمستخدم معين) ════
        if cmd == ".قبول" and event.is_reply:
            reply = await event.get_reply_message()
            accepted_users.add(reply.sender_id)
            welcomed_users.discard(reply.sender_id)
            try:
                await event.delete()
            except Exception:
                pass
            return

        # ════ إذاعة خاص ════
        if cmd == ".اذاعة_خاص":
            if not args:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة_خاص <الرسالة>`")
                return
            msg = " ".join(args)
            count = 0
            await reply_or_edit(event, "📢 جاري الإذاعة للمحادثات الخاصة...")
            async for dialog in client.iter_dialogs():
                if dialog.is_user and dialog.entity.id != owner_id and not getattr(dialog.entity, 'bot', False):
                    try:
                        await client.send_message(dialog.entity, msg)
                        count += 1
                        await asyncio.sleep(1)
                    except Exception:
                        pass
            await reply_or_edit(event, f"✅ تم الإرسال لـ {count} محادثة خاصة!")
            return

        # ════ إذاعة جروب ════
        if cmd == ".اذاعة_جروب":
            if not args:
                await reply_or_edit(event, "⚠️ الاستخدام: `.اذاعة_جروب <الرسالة>`")
                return
            msg = " ".join(args)
            count = 0
            await reply_or_edit(event, "📢 جاري الإذاعة للمجموعات...")
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    try:
                        await client.send_message(dialog.entity, msg)
                        count += 1
                        await asyncio.sleep(1)
                    except Exception:
                        pass
            await reply_or_edit(event, f"✅ تم الإرسال لـ {count} مجموعة!")
            return

        # ════ تتبع قناة ════
        if cmd == ".تتبع_قناة":
            if len(args) < 2:
                await reply_or_edit(event, "⚠️ الاستخدام: `.تتبع_قناة @قناة_المصدر @قناة_الاستلام`")
                return
            try:
                src = await client.get_entity(args[0].lstrip('@'))
                dst = await client.get_entity(args[1].lstrip('@'))
                tracked_channels[src.id] = dst.id
                await reply_or_edit(event,
                    f"✅ بدأ التتبع!\n"
                    f"📡 المصدر: {src.title}\n"
                    f"📥 الاستلام: {dst.title}\n\n"
                    f"🔍 هيستخرج أي رقم بصيغة `*858*XXXXXX#` تلقائياً"
                )
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
            return

        # ════ وقف التتبع ════
        if cmd == ".وقف_التتبع":
            tracked_channels.clear()
            await reply_or_edit(event, "🛑 تم إيقاف تتبع القنوات!")
            return

        # ══════════════════════════════════════════
        #     أوامر الحماية (جروبات فقط)
        # ══════════════════════════════════════════
        if not event.is_group:
            return

        # ════ حظر ════
        if cmd == ".حظر":
            target_id = await resolve_target(event, args)
            if not target_id:
                return
            try:
                await client.edit_permissions(event.chat_id, target_id, view_messages=False)
                await reply_or_edit(event, "🚫 تم حظر المستخدم بنجاح!")
            except ChatAdminRequiredError:
                await reply_or_edit(event, "❌ محتاج صلاحية حظر الأعضاء!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
            return

        # ════ فك حظر ════
        if cmd == ".فكحظر":
            target_id = await resolve_target(event, args)
            if not target_id:
                return
            try:
                await client.edit_permissions(event.chat_id, target_id, view_messages=True)
                await reply_or_edit(event, "✅ تم فك حظر المستخدم!")
            except ChatAdminRequiredError:
                await reply_or_edit(event, "❌ محتاج صلاحية!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
            return

        # ════ كتم (تقييد + حذف رسائله) ════
        if cmd == ".كتم" and not text.startswith(".كتم_مشرف"):
            target_id = await resolve_target(event, args)
            if not target_id:
                return
            try:
                await client.edit_permissions(event.chat_id, target_id, send_messages=False)
                deleted = 0
                async for msg in client.iter_messages(event.chat_id, from_user=target_id, limit=100):
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
                await reply_or_edit(event, f"🔇 تم كتم المستخدم وحذف {deleted} رسالة!")
            except ChatAdminRequiredError:
                await reply_or_edit(event, "❌ محتاج صلاحية!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
            return

        # ════ فك كتم ════
        if cmd == ".فككتم":
            target_id = await resolve_target(event, args)
            if not target_id:
                return
            try:
                await client.edit_permissions(event.chat_id, target_id, send_messages=True)
                await reply_or_edit(event, "🔊 تم فك كتم المستخدم!")
            except ChatAdminRequiredError:
                await reply_or_edit(event, "❌ محتاج صلاحية!")
            except Exception as e:
                await reply_or_edit(event, f"❌ خطأ: {e}")
            return

        # ════ كتم مشرف (حذف رسائله تلقائياً) ════
        if cmd == ".كتم_مشرف":
            if not event.is_reply:
                await reply_or_edit(event, "⚠️ رد على رسالة المشرف عشان تكتمه!")
                return
            reply = await event.get_reply_message()
            target_id = reply.sender_id
            if event.chat_id not in muted_admins:
                muted_admins[event.chat_id] = set()
            muted_admins[event.chat_id].add(target_id)
            await reply_or_edit(event, "🔇 تم كتم المشرف! رسائله هتتحذف تلقائياً")
            return

        # ════ فك كتم مشرف ════
        if cmd == ".فك_كتم_مشرف":
            if not event.is_reply:
                await reply_or_edit(event, "⚠️ رد على رسالة المشرف عشان تفك كتمه!")
                return
            reply = await event.get_reply_message()
            target_id = reply.sender_id
            if event.chat_id in muted_admins:
                muted_admins[event.chat_id].discard(target_id)
            await reply_or_edit(event, "🔊 تم فك كتم المشرف!")
            return

    # ══════════════════════════════════════════
    #    حذف رسائل المشرفين المكتومين
    # ══════════════════════════════════════════
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group))
    async def delete_muted_admin_msgs(event):
        if not muted_admins:
            return
        chat_id = event.chat_id
        if chat_id not in muted_admins:
            return
        if event.sender_id in muted_admins[chat_id]:
            try:
                await event.delete()
            except Exception:
                pass

    logging.info(f"✅ كل الهاندلرز اشتغلوا - {me.first_name}")
    print(f"✅ كل الهاندلرز اشتغلوا - {me.first_name}")