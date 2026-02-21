"""
بوت أغاني بسيط
بتبعتله: Pyrogram Session + Telethon Session
وهو يشغل أغاني في الجروب
"""
import os, asyncio, glob, logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from pyrofork import Client as PyroClient
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)

# ══════════════════════════════
# ضيف الإعدادات هنا
# ══════════════════════════════
API_ID           = 21173110
API_HASH         = "71db0c8aae15effc04dcfc636e68c349"
TELETHON_SESSION = "1BJWap1wBuyRaZ5yKsurQ_R9mKEEUWzW7c3WtC0AUfUwjRDlHDm5ZF4xGALM7HoKXHsMSMCCTmLsYNSYwn0u1iaWqJimbpX6cwjDLidvJHZccLP0Hv1B3_e1ngs4hFaIUkM9ieM3ivgRZyx0OzJWHXH8z1SJ4C6Crj8-XzQyywa_kdRjgJ7ICwA74eAmaXLX3ldTiGhax_N3CvdbnpNjJ-GFP7xnYXQT432rjyYDJbRlyH13edln7qFRKjrUykyM_2ir3Yq6RZRlqIxiSX87LuxOnDMXR826yVnd2rcp289ZZULXTFYUIJyr_ShcUi7M22mIDrNlaR4BsfezMU_Xz3HRGYZMPkho="
PYROGRAM_SESSION = "BAGOXzsAY2IZkkdbaL7f80ukOhwdLcEzj0r7QLYvq2c7Aq6cWDadPvHWTGmh1UTEgY4PcuU7eI8Ewoa5mvLaYfhKmoNoWHz0kvk4G1vUnVs-WT_x5JDONtCNX9N8Op1bl8Q-VIXlzs40mb8zJ7w5my08ab3bazAqfkEesSjLUiGatkh3FRTKFBpSyxOZMNoQspTniv9Ou86UnOXlLAefamYo-7M4IKIkZInZd_tvFpzM8PYr7er6hapjgGGIGmH6IrW2uco9H44IATu5MeHliIgO4nmD3nvv6VN2ra8-fkqVZfxTZtSUFNOOjmVOORDhbqfxRmhaPAU4qZKuBOozwqKDomPKZAAAAAHYtkk7AA"

os.makedirs("downloads", exist_ok=True)

# قوايم التشغيل
queues = {}

def get_q(cid):
    if cid not in queues:
        queues[cid] = []
    return queues[cid]


async def download(query, chat_id):
    """بحث وتحميل من يوتيوب"""
    is_url = "youtube.com" in query or "youtu.be" in query
    opts = {
        "format": "bestaudio/best",
        "outtmpl": f"downloads/{chat_id}_%(id)s.%(ext)s",
        "quiet": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
    }
    def _dl():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query if is_url else f"ytsearch:{query}", download=True)
            if "entries" in info:
                info = info["entries"][0]
            files = glob.glob(f"downloads/{chat_id}_{info['id']}*")
            m, s = divmod(int(info.get("duration", 0)), 60)
            return files[0], info.get("title", "?"), f"{m}:{s:02d}"
    return await asyncio.get_event_loop().run_in_executor(None, _dl)


async def main():
    # تشغيل Telethon
    tg = TelegramClient(StringSession(TELETHON_SESSION), API_ID, API_HASH)
    await tg.start()
    me = await tg.get_me()
    logger.info(f"✅ Telethon: {me.first_name}")

    # تشغيل PyTgCalls
    pyro = PyroClient("pyro", api_id=API_ID, api_hash=API_HASH, session_string=PYROGRAM_SESSION)
    call = PyTgCalls(pyro)
    await pyro.start()
    await call.start()
    logger.info("✅ PyTgCalls ready")

    @tg.on(events.NewMessage(pattern=r"^\.play (.+)"))
    async def play(event):
        if not event.is_group:
            return
        query = event.pattern_match.group(1).strip()
        msg = await event.respond("🔍 جاري البحث...")
        try:
            file, title, dur = await download(query, event.chat_id)
            q = get_q(event.chat_id)
            track = {"file": file, "title": title, "dur": dur}

            if not q:
                q.append(track)
                await call.play(event.chat_id, MediaStream(file))
                await msg.edit(f"🎵 **{title}**\n⏱ {dur}")
            else:
                q.append(track)
                await msg.edit(f"✅ **{title}**\n📍 في القايمة ({len(q)})")
        except Exception as e:
            await msg.edit(f"❌ {e}")

    @tg.on(events.NewMessage(pattern=r"^\.شغل (.+)"))
    async def play_ar(event):
        event.pattern_match = type("m", (), {"group": lambda s, i: event.raw_text.split(maxsplit=1)[1]})()
        await play(event)

    @tg.on(events.NewMessage(pattern=r"^\.(pause|وقف)$"))
    async def pause(event):
        if not event.is_group: return
        try:
            await call.pause(event.chat_id)
            await event.respond("⏸")
        except Exception as e:
            await event.respond(f"❌ {e}")

    @tg.on(events.NewMessage(pattern=r"^\.(resume|كمل)$"))
    async def resume(event):
        if not event.is_group: return
        try:
            await call.resume(event.chat_id)
            await event.respond("▶️")
        except Exception as e:
            await event.respond(f"❌ {e}")

    @tg.on(events.NewMessage(pattern=r"^\.(skip|تخطي)$"))
    async def skip(event):
        if not event.is_group: return
        q = get_q(event.chat_id)
        if q: q.pop(0)
        if q:
            nxt = q[0]
            try:
                await call.play(event.chat_id, MediaStream(nxt["file"]))
                await event.respond(f"⏭ **{nxt['title']}**")
            except Exception as e:
                await event.respond(f"❌ {e}")
        else:
            try:
                await call.leave_call(event.chat_id)
            except Exception:
                pass
            await event.respond("⏹ خلصت القايمة")

    @tg.on(events.NewMessage(pattern=r"^\.(stop|ستوب)$"))
    async def stop(event):
        if not event.is_group: return
        queues.pop(event.chat_id, None)
        try:
            await call.leave_call(event.chat_id)
        except Exception:
            pass
        for f in glob.glob(f"downloads/{event.chat_id}_*"):
            try: os.remove(f)
            except: pass
        await event.respond("⏹ تم الإيقاف")

    @tg.on(events.NewMessage(pattern=r"^\.(queue|قايمة|q)$"))
    async def queue_cmd(event):
        if not event.is_group: return
        q = get_q(event.chat_id)
        if not q:
            await event.respond("📋 القايمة فاضية")
            return
        lines = ["🎵 **القايمة:**"]
        for i, t in enumerate(q):
            lines.append(f"{'▶️' if i==0 else f'{i+1}.'} {t['title']} | {t['dur']}")
        await event.respond("\n".join(lines))

    @tg.on(events.NewMessage(pattern=r"^\.(now|np|الحالية)$"))
    async def now(event):
        if not event.is_group: return
        q = get_q(event.chat_id)
        if q:
            await event.respond(f"🎧 **{q[0]['title']}**\n⏱ {q[0]['dur']}")
        else:
            await event.respond("📭 مفيش أغنية")

    @tg.on(events.NewMessage(pattern=r"^\.الاوامر$"))
    async def cmds(event):
        await event.respond(
            "🎵 **أوامر الموسيقى:**\n"
            "`.play <اسم/رابط>` — شغل\n"
            "`.شغل <اسم>` — نفس الأمر بالعربي\n"
            "`.pause` / `.وقف` — وقّف\n"
            "`.resume` / `.كمل` — كمّل\n"
            "`.skip` / `.تخطي` — التالية\n"
            "`.stop` / `.ستوب` — وقّف كل شيء\n"
            "`.queue` / `.قايمة` — القايمة\n"
            "`.now` / `.الحالية` — الحالية"
        )

    logger.info("✅ البوت شغال! اكتب .play في أي جروب")
    await tg.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())