"""
🎵 Telegram Voice Chat Music Bot
===================================
المتطلبات (Requirements):
    pip install pyrogram tgcalls yt-dlp python-dotenv

إعداد ملف .env:
    API_ID=your_api_id
    API_HASH=your_api_hash
    BOT_TOKEN=your_bot_token

الأوامر:
    /play <اسم الأغنية> — بحث وتشغيل أغنية في الـ Voice Chat
    /stop              — إيقاف التشغيل والخروج من الـ Voice Chat
    /ping              — للتأكد إن البوت شغال
"""

import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio

# ─── إعدادات البوت ────────────────────────────────────────────────────────────
# ⚠️ دي بيانات وهمية للتوضيح فقط — حط بياناتك الحقيقية هنا
API_ID    = 21173110
API_HASH  = "71db0c8aae15effc04dcfc636e68c349"
BOT_TOKEN = "5715894811:AAEn1rgGrt98NbqlkcGPyz0As4mLv_I65qw"

# ─── تهيئة الـ Clients ────────────────────────────────────────────────────────
app      = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)


# ─── دالة البحث وتحميل الأغنية ───────────────────────────────────────────────
def search_and_get_url(song_name: str) -> dict | None:
    """
    بيبحث عن الأغنية على يوتيوب ويرجع معلوماتها (عنوان + رابط الصوت).
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "ytsearch1",   # أول نتيجة بحث
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=False)
            if info and "entries" in info and info["entries"]:
                entry = info["entries"][0]
                return {
                    "title": entry.get("title", "غير معروف"),
                    "url":   entry["url"],
                    "duration": entry.get("duration", 0),
                }
        except Exception as e:
            print(f"[yt-dlp] خطأ: {e}")
    return None


# ─── أمر /start ───────────────────────────────────────────────────────────────
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "🎵 **أهلاً وسهلاً!**\n\n"
        "أنا بوت الموسيقى بتاعك 🎧\n\n"
        "**الأوامر المتاحة:**\n"
        "▶️ `/play اسم الأغنية` — بحث وتشغيل أغنية في الـ Voice Chat\n"
        "⏹ `/stop` — إيقاف التشغيل والخروج\n"
        "🏓 `/ping` — التأكد إن البوت شغال\n\n"
        "جرب دلوقتي! ابعت `/play فيروز` مثلاً 🎶"
    )


# ─── أمر /ping ────────────────────────────────────────────────────────────────
@app.on_message(filters.command("ping"))
async def ping(_, message: Message):
    await message.reply_text("🏓 Pong! البوت شغال.")


# ─── أمر /play ────────────────────────────────────────────────────────────────
@app.on_message(filters.command("play") & filters.group)
async def play(_, message: Message):
    # التحقق من وجود اسم أغنية
    if len(message.command) < 2:
        await message.reply_text("❗ استخدم الأمر كده:\n`/play اسم الأغنية`")
        return

    song_name = " ".join(message.command[1:])
    chat_id   = message.chat.id

    status_msg = await message.reply_text(f"🔍 بدور على: **{song_name}**...")

    # البحث عن الأغنية
    result = search_and_get_url(song_name)
    if not result:
        await status_msg.edit_text("❌ معقدرتش أجيب الأغنية دي. جرب اسم تاني.")
        return

    title    = result["title"]
    audio_url = result["url"]
    duration  = result["duration"]
    mins, secs = divmod(duration, 60)

    await status_msg.edit_text(f"🎵 بشغّل: **{title}** ({mins}:{secs:02d})")

    # الانضمام للـ Voice Chat وتشغيل الأغنية
    try:
        await pytgcalls.join_group_call(
            chat_id,
            AudioPiped(audio_url, HighQualityAudio()),
        )
    except Exception as e:
        # لو البوت بالفعل في الـ VC، غيّر الأغنية الحالية
        try:
            await pytgcalls.change_stream(
                chat_id,
                AudioPiped(audio_url, HighQualityAudio()),
            )
        except Exception as inner_e:
            await status_msg.edit_text(f"❌ حصل خطأ: {inner_e}")
            return

    await status_msg.edit_text(
        f"▶️ بيشغّل دلوقتي:\n🎵 **{title}**\n⏱ المدة: {mins}:{secs:02d}"
    )


# ─── أمر /stop ────────────────────────────────────────────────────────────────
@app.on_message(filters.command("stop") & filters.group)
async def stop(_, message: Message):
    chat_id = message.chat.id
    try:
        await pytgcalls.leave_group_call(chat_id)
        await message.reply_text("⏹ وقفت التشغيل وخرجت من الـ Voice Chat.")
    except Exception as e:
        await message.reply_text(f"❌ مش قادر أوقف: {e}")


# ─── تشغيل البوت ─────────────────────────────────────────────────────────────
async def main():
    print("✅ البوت شغّال!")
    await pytgcalls.start()
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())