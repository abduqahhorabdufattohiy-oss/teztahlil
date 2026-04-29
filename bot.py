import logging
import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from finvizfinance.quote import finvizfinance

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SECTOR_MAP = {
    "Technology": "Texnologiya",
    "Financial": "Moliya",
    "Healthcare": "Sog‘liqni saqlash",
    "Consumer Cyclical": "Iste’mol tovarlari (siklik)",
    "Consumer Defensive": "Iste’mol tovarlari (himoyalangan)",
    "Energy": "Energetika",
    "Communication Services": "Aloqa xizmatlari",
    "Industrials": "Sanoat",
    "Basic Materials": "Xomashyo",
    "Real Estate": "Ko‘chmas mulk",
    "Utilities": "Kommunal xizmatlar"
}

def clean_value(val):
    if val in ['-', 'N/A', None]: 
        return "0"
    return str(val).replace(',', '').replace('%', '')

def get_full_analysis(f):
    try:
        price = f.get('Price', '0')
        change = f.get('Change', '0')
        raw_sector = f.get('Sector', 'N/A')
        uzb_sector = SECTOR_MAP.get(raw_sector, raw_sector)
        formatted_sector = f"<b>{raw_sector.upper()}</b> ({uzb_sector.upper()})"

        mcap = f.get('Market Cap', 'N/A')
        pe = f.get('P/E', 'N/A')
        div = f.get('Dividend %', 'N/A')
        eps = f.get('EPS (ttm)', 'N/A')
        
        debt_eq_raw = clean_value(f.get('Debt/Eq', '0'))
        try:
            debt_eq = float(debt_eq_raw)
        except ValueError:
            debt_eq = 0.0

        industry = f.get('Industry', '')
        non_compliant_industries = ['Banks', 'Insurance', 'Gambling', 'Tobacco']
        
        if any(x in industry for x in non_compliant_industries):
            shariah = "NOJOIZ"
        elif debt_eq > 0.33:
            shariah = "SHUBHALI"
        else:
            shariah = "JOIZ"

        rsi = clean_value(f.get('RSI (14)', '0'))
        sma200 = clean_value(f.get('SMA200', '0'))
        sma50 = clean_value(f.get('SMA50', '0'))
        sma20 = clean_value(f.get('SMA20', '0'))

        analysis = (
            f"<b>FUNDAMENTAL</b>\n"
            f"<b>M.CAP:</b> {mcap} | <b>P/E:</b> {pe}\n"
            f"<b>DIVIDEND:</b> {div} | <b>EPS:</b> {eps}\n\n"
            f"<b>TECHNICAL</b>\n"
            f"<b>RSI:</b> {rsi} | <b>SMA200:</b> {sma200}\n"
            f"<b>SMA50:</b> {sma50} | <b>SMA20:</b> {sma20}\n"
            f"—\n"
            f"<b>SHARI’AT STATUSI:</b> {shariah}"
        )
        return analysis, formatted_sector, price, change
    except Exception as e:
        logger.error(f"Error in analysis: {e}")
        return "Tahlil jarayonida xatolik.", "N/A", "0", "0%"

async def handle_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text.startswith('$'):
        return

    ticker = text[1:].upper()
    if not ticker.isalnum():
        return

    status_msg = await update.message.reply_text(f"QIDIRILMOQDA: {ticker}...")

    try:
        stock = finvizfinance(ticker)
        fundament = stock.ticker_fundament()

        if not fundament:
            await status_msg.edit_text("ma’lumot topilmadi.")
            return

        now = datetime.now(timezone.utc) + timedelta(hours=5)
        dt_str = now.strftime('%d.%m.%Y | %H:%M')

        chart_url = f"https://charts2.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&rev={int(time.time())}"
        analysis_text, sector_info, price, change = get_full_analysis(fundament)

        caption = (
            f"<b>SANA:</b> {dt_str} (UZB)\n\n"
            f"<b>TICKER:</b> ${ticker} | <b>PRICE:</b> {price} ({change})\n"
            f"<b>SECTOR:</b> {sector_info}\n"
            f"—\n"
            f"{analysis_text}"
        )

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("FINVIZ", url=f"https://finviz.com/quote.ashx?t={ticker}"),
            InlineKeyboardButton("ISLAMICLY", url="https://www.islamicly.com/home/stocks")
        ]])

        try:
            await update.message.reply_photo(photo=chart_url, caption=caption, parse_mode='HTML', reply_markup=kb)
        except Exception:
            await update.message.reply_text(caption, parse_mode='HTML', reply_markup=kb)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Request error ({ticker}): {e}")
        await status_msg.edit_text("Xatolik yuz berdi yoki ma'lumot topilmadi.")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN topilmadi!")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("marhamat! $ticker yuborishingiz mumkin")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\$'), handle_request))

    logger.info("bot ishga tushdi.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()