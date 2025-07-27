import io
import logging
from telebot import types, TeleBot
from pytubefix import YouTube
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token - Replace with your actual bot token
BOT_TOKEN = '7512725094:AAHpsyKM1ifxzGlW30Boi_uoeo0EBFgfR8k'  # Replace this with your actual bot token from @BotFather

if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    raise ValueError("Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")

bot = TeleBot(BOT_TOKEN)

def is_youtube_url(url):
    """Check if the provided URL is a valid YouTube URL"""
    youtube_regex = re.compile(
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\n]{11})'
    )
    return youtube_regex.match(url) is not None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handle /start and /help commands"""
    welcome_text = """
🎥 *YouTube Video Downloader Bot*

Welcome! I can help you download YouTube videos.

*How to use:*
1. Send me a YouTube link
2. I'll download and send you the video

*Supported formats:*
- youtube.com/watch?v=...
- youtu.be/...
- youtube.com/embed/...

Just paste any YouTube link and I'll handle the rest! 📹
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def download_video(message: types.Message):
    """Handle text messages and download YouTube videos"""
    
    # Check if the message contains a YouTube URL
    if not is_youtube_url(message.text.strip()):
        bot.reply_to(message, "❌ Please send a valid YouTube URL.\n\nExample: https://www.youtube.com/watch?v=...")
        return
    
    # Send processing message
    processing_msg = bot.reply_to(message, "⏳ Processing your video... Please wait.")
    
    try:
        # Create YouTube object
        yt = YouTube(message.text.strip())
        
        # Get video info
        title = yt.title
        duration = yt.length
        
        # Format duration
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        
        if hours > 0:
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes}:{seconds:02d}"
        
        # Check video duration (limit to 6 hours)
        if duration > 21600:  # 6 hours
            bot.edit_message_text(
                "❌ Video is too long (>6 hours). Please try a shorter video.",
                processing_msg.chat.id,
                processing_msg.message_id
            )
            return
        
        # Update processing message with video info
        bot.edit_message_text(
            f"📹 *{title}*\n⏱ Duration: {duration_str}\n\n⬇️ Downloading...",
            processing_msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
        # Download video to buffer
        buffer = io.BytesIO()
        
        # Try to get the best progressive stream first
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not stream:
            # Fallback to any progressive stream
            stream = yt.streams.filter(progressive=True).first()
        
        if not stream:
            # Final fallback to lowest resolution
            stream = yt.streams.get_lowest_resolution()
        
        if not stream:
            bot.edit_message_text(
                "❌ No downloadable streams found for this video.",
                processing_msg.chat.id,
                processing_msg.message_id
            )
            return
        
        # Check approximate file size
        if hasattr(stream, 'filesize') and stream.filesize:
            file_size_mb = stream.filesize / (1024 * 1024)
            if file_size_mb > 2000:  # 2GB Telegram limit
                bot.edit_message_text(
                    f"❌ Video file is too large ({file_size_mb:.1f}MB).\nTelegram limit is 2GB.",
                    processing_msg.chat.id,
                    processing_msg.message_id
                )
                return
        
        # Download to buffer
        stream.stream_to_buffer(buffer)
        buffer.seek(0)
        
        # Update message for upload
        bot.edit_message_text(
            f"📹 *{title}*\n⏱ Duration: {duration_str}\n\n📤 Uploading...",
            processing_msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
        # Send video
        bot.send_video(
            message.chat.id,
            buffer.getvalue(),
            caption=f"🎬 {title}\n⏱ {duration_str}",
            reply_to_message_id=message.message_id
        )
        
        # Delete processing message
        bot.delete_message(processing_msg.chat.id, processing_msg.message_id)
        
        logger.info(f"Successfully downloaded and sent video: {title}")
        
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        
        error_message = "❌ Sorry, I couldn't download this video.\n\n"
        
        if "unavailable" in str(e).lower():
            error_message += "The video might be private, deleted, or geo-restricted."
        elif "403" in str(e):
            error_message += "Access denied. The video might be age-restricted or private."
        elif "timeout" in str(e).lower():
            error_message += "Download timeout. Please try again."
        else:
            error_message += "Please try again later or with a different video."
        
        bot.edit_message_text(
            error_message,
            processing_msg.chat.id,
            processing_msg.message_id
        )
    
    finally:
        # Clean up buffer
        if 'buffer' in locals():
            buffer.close()

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice'])
def handle_media(message):
    """Handle non-text media messages"""
    bot.reply_to(message, "📝 Please send me a YouTube link as text message.")

if __name__ == "__main__":
    logger.info("Starting YouTube Downloader Bot...")
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        raise
