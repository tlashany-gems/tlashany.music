"""
🎵 Telegram Voice Chat Music Bot (Userbot)
==========================================
Variables على Railway:
    API_ID         = من my.telegram.org
    API_HASH       = من my.telegram.org
    BOT_TOKEN      = من @BotFather
    STRING_SESSION = الـ session string بتاع حسابك
"""

import os
import asyncio
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream

# ─── إعدادات ──────────────────────────────────────────────────────────────────
API_ID         = int(os.environ.get("API_ID", "0"))
API_HASH       = os.environ.get("API_HASH", "")
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

# ─── تهيئة الـ Clients ────────────────────────────────────────────────────────
userbot = Client(
    name="userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

bot = Client(
    name="bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

call = PyTgCalls(userbot)


# ─── البحث عن الأغنية ────────────────────────────────────────────────────────
def search_song(song_name: str) -> dict | None:
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=False)
            if info and "entries" in info and info["entries"]:
                entry = info["entries"][0]
                return {
                    "title":    entry.get("title", "غير معروف"),
                    "url":      entry["url"],
                    "duration": entry.get("duration", 0),
                }
        except Exception as e:
            print(f"[yt-dlp error] {e}")
    return None


# ─── /start ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "🎵 **أهلاً وسهلاً!**\n\n"
        "أنا بوت الموسيقى بتاعك 🎧\n\n"
        "**الأوامر المتاحة:**\n"
        "▶️ `/play اسم الأغنية` — بحث وتشغيل في الـ Voice Chat\n"
        "⏹ `/stop` — إيقاف التشغيل والخروج\n"
        "🏓 `/ping` — التأكد إن البوت شغال\n\n"
        "جرب دلوقتي! ابعت `/play فيروز` مثلاً 🎶"
    )


# ─── /ping ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("ping"))
async def ping(_, message: Message):
    await message.reply_text("🏓 Pong! البوت شغال.")


# ─── /play ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("play") & filters.group)
async def play(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❗ استخدم الأمر كده:\n`/play اسم الأغنية`")
        return

    song_name  = " ".join(message.command[1:])
    chat_id    = message.chat.id
    status     = await message.reply_text(f"🔍 بدور على: **{song_name}**...")

    result = search_song(song_name)
    if not result:
        await status.edit_text("❌ معقدرتش أجيب الأغنية دي. جرب اسم تاني.")
        return

    title      = result["title"]
    url        = result["url"]
    mins, secs = divmod(result["duration"], 60)

    try:
        await call.play(chat_id, MediaStream(url))
    except Exception as e:
        await status.edit_text(f"❌ حصل خطأ: {e}")
        return

    await status.edit_text(
        f"▶️ بيشغّل دلوقتي:\n"
        f"🎵 **{title}**\n"
        f"⏱ المدة: {mins}:{secs:02d}"
    )


# ─── /stop ────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("stop") & filters.group)
async def stop(_, message: Message):
    try:
        await call.leave_call(message.chat.id)
        await message.reply_text("⏹ وقفت التشغيل وخرجت من الـ Voice Chat.")
    except Exception as e:
        await message.reply_text(f"❌ مش قادر أوقف: {e}")


# ─── تشغيل البوت ─────────────────────────────────────────────────────────────
async def main():
    print("✅ البوت شغّال!")
    await userbot.start()
    await bot.start()
    await call.start()
    await idle()

if __name__ == "__main__":
    asyncio.run(main())