import os
import re
import uuid
import cloudscraper
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "6454975881:AAFkvRqo7QWZUZPaIqpBvgLNsNJ56n5IjsQ"


def get_hd_url(tiktok_url: str) -> str | None:
    scraper = cloudscraper.create_scraper()

    r = scraper.post(
        "https://tiksave.io/api/ajaxSearch",
        data={"q": tiktok_url, "lang": "en"},
        headers={
            "Origin": "https://tiksave.io",
            "Referer": "https://tiksave.io/en",
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    if r.status_code != 200:
        return None

    data = r.json()
    if data.get("status") != "ok":
        return None

    html = data["data"]

    # جيب رابط snapcdn الخاص بـ HD
    match = re.search(
        r'href="(https://dl\.snapcdn\.app/get\?token=[^"]+)"[^>]*>\s*<i[^>]*></i>\s*Download MP4 HD',
        html
    )
    if match:
        return match.group(1)

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً!\nأرسل رابط TikTok وأنا أرسل لك الفيديو HD بدون علامة مائية 🎬"
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "tiktok.com" not in url:
        await update.message.reply_text("❌ أرسل رابط TikTok صحيح!")
        return

    msg = await update.message.reply_text("⏳ جاري المعالجة...")
    output_path = f"/tmp/{uuid.uuid4().hex}.mp4"

    try:
        # ① جيب رابط snapcdn HD
        import asyncio
        loop = asyncio.get_event_loop()
        video_url = await loop.run_in_executor(None, get_hd_url, url)

        if not video_url:
            await msg.edit_text("❌ ما قدرت أجيب رابط الفيديو.")
            return

        await msg.edit_text("📥 جاري التحميل...")

        # ② حمّل الفيديو من snapcdn
        scraper = cloudscraper.create_scraper()
        r = scraper.get(video_url, stream=True)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        await msg.edit_text("📤 جاري الإرسال...")

        with open(output_path, "rb") as vf:
            await update.message.reply_video(
                video=vf,
                caption="🎬 HD | بدون علامة مائية",
                supports_streaming=True,
                width=720,
                height=1280,
            )

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ صار خطأ:\n{str(e)[:300]}")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
print("✅ البوت شغال!")
app.run_polling()
