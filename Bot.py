import os
import re
import logging
import tempfile
from pathlib import Path

import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# -------------------- Logging --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- Config --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")

URL_REGEX = re.compile(r"(https?://\S+)", re.IGNORECASE)

# -------------------- Handlers --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام!\n"
        "لینک ویدیو را بفرست تا تلاش کنم آن را دانلود و ارسال کنم.\n"
        "مثال:\n"
        "https://example.com/video"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "راهنما:\n"
        "1) لینک ویدیو را بفرست\n"
        "2) من دانلود می‌کنم\n"
        "3) اگر فایل خیلی بزرگ نباشد، برایت ارسال می‌شود\n\n"
        "دستورات:\n"
        "/start - شروع\n"
        "/help - راهنما"
    )


def extract_url(text: str):
    match = URL_REGEX.search(text or "")
    return match.group(1) if match else None


def download_video(url: str) -> Path:
    """
    Downloads video with yt-dlp and returns path to downloaded file.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="bot_download_"))
    outtmpl = str(temp_dir / "%(title).80s-%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

    # If merged to mp4, ensure final file path
    if file_path.endswith(".webm") or file_path.endswith(".mkv"):
        possible_mp4 = Path(file_path).with_suffix(".mp4")
        if possible_mp4.exists():
            return possible_mp4

    return Path(file_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = extract_url(update.message.text)
    if not url:
        await update.message.reply_text("لطفاً فقط یک لینک معتبر ارسال کن.")
        return

    msg = await update.message.reply_text("در حال دانلود و پردازش ویدیو... لطفاً صبر کن.")

    try:
        # دانلود در thread جداگانه بهتر است، اما برای نسخه ساده مستقیم می‌زنیم
        # اگر خواستی نسخه حرفه‌ای با asyncio.to_thread هم می‌دهم
        file_path = download_video(url)

        if not file_path.exists():
            await msg.edit_text("دانلود انجام شد اما فایل پیدا نشد.")
            return

        size_mb = file_path.stat().st_size / (1024 * 1024)

        if size_mb > 45:
            await msg.edit_text(
                f"فایل دانلود شد اما حجم آن حدود {size_mb:.1f}MB است و ممکن است برای ارسال مستقیم مناسب نباشد."
            )
            # می‌توانیم اینجا فایل را فقط بفرستیم به صورت document یا راهکارهای دیگر اضافه کنیم
            await update.message.reply_document(document=file_path.open("rb"))
        else:
            await update.message.reply_video(video=file_path.open("rb"))

        await msg.delete()

    except Exception as e:
        logger.exception("Error while processing video")
        await msg.edit_text(f"خطا در پردازش لینک:\n{e}")


# -------------------- Main --------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # For local test:
    # app.run_polling()

    # For Render production:
    port = int(os.environ.get("PORT", "10000"))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=os.environ.get("WEBHOOK_URL", "").rstrip("/") + "/" + BOT_TOKEN if os.environ.get("WEBHOOK_URL") else None,
    )


if __name__ == "__main__":
    main()
