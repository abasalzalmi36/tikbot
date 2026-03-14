import os
import re
import uuid
import asyncio
import cloudscraper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = "6454975881:AAFkvRqo7QWZUZPaIqpBvgLNsNJ56n5IjsQ"


def fetch_options(tiktok_url: str) -> dict | None:
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
    options = {}

    # Full HD
    hd = re.search(
        r'href="(https://dl\.snapcdn\.app/get\?token=[^"]+)"[^>]*>\s*<i[^>]*></i>\s*Download MP4 HD',
        html
    )
    if hd:
        options["Full HD 🎬"] = hd.group(1)

    # جودة عادية - خذ أول رابط MP4 بس
    normal = re.search(
        r'href="(https://(?:dl\.snapcdn\.app/get\?token=|[^"]*tiktokcdn[^"]*)[^"]+)"[^>]*>\s*<i[^>]*></i>\s*Download MP4 \[1\]',
        html
    )
    if normal:
        options["SD 📱"] = normal.group(1)

    # MP3
    mp3 = re.search(
        r'href="(https://dl\.snapcdn\.app/get\?token=[^"]+)"[^>]*>\s*<i[^>]*></i>\s*Download MP3',
        html
    )
    if mp3:
        options["MP3 🎵"] = mp3.group(1)

    return options if options else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً!\nأرسل رابط TikTok وأنا أعطيك خيارات التحميل 🎬"
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "tiktok.com" not in url:
        await update.message.reply_text("❌ أرسل رابط TikTok صحيح!")
        return

    msg = await update.message.reply_text("⏳ جاري المعالجة...")

    loop = asyncio.get_event_loop()
    options = await loop.run_in_executor(None, fetch_options, url)

    if not options:
        await msg.edit_text("❌ ما قدرت أجيب خيارات الفيديو.")
        return

    context.bot_data[url] = options

    buttons = [
        [InlineKeyboardButton(label, callback_data=f"{url}||{label}")]
        for label in options
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await msg.edit_text("اختار الجودة:", reply_markup=keyboard)


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if "||" not in data:
        return

    tiktok_url, label = data.split("||", 1)
    options = context.bot_data.get(tiktok_url)

    if not options or label not in options:
        await query.edit_message_text("❌ انتهت صلاحية الخيارات، أرسل الرابط مرة ثانية.")
        return

    video_url = options[label]
    is_mp3 = "MP3" in label

    await query.edit_message_text(f"📥 جاري تحميل {label}...")

    output_path = f"./{uuid.uuid4().hex}.{'mp3' if is_mp3 else 'mp4'}"

    try:
        scraper = cloudscraper.create_scraper()
        r = scraper.get(video_url, stream=True)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        await query.edit_message_text("📤 جاري الإرسال...")

        with open(output_path, "rb") as f:
            if is_mp3:
                await query.message.reply_audio(
                    audio=f,
                    caption="🎵 MP3",
                )
            else:
                await query.message.reply_video(
                    video=f,
                    caption=f"🎬 {label} | بدون علامة مائية",
                    supports_streaming=True,
                    width=720,
                    height=1280,
                )

        await query.delete_message()

    except Exception as e:
        await query.edit_message_text(f"❌ صار خطأ:\n{str(e)[:300]}")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
app.add_handler(CallbackQueryHandler(handle_button))
print("✅ البوت شغال!")
app.run_polling()
