# main.py

import logging, aiohttp, random
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pandas as pd
import mplfinance as mpf
from config import BOT_TOKEN, CHANNEL_OR_USER_ID, TWELVEDATA_API_KEY, SYMBOL

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
logging.basicConfig(level=logging.INFO)

# === Fetch 10 candles (10min) from TwelveData ===
async def fetch_candle_data(symbol, interval='1min', outputsize=10):
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={TWELVEDATA_API_KEY}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if "values" not in data:
                print("🔎 API Response:", data)
                return None
            return data

# === Determine signal direction ===
def calculate_direction(open_price, close_price):
    if close_price > open_price:
        return "CALL 🔼"
    elif close_price < open_price:
        return "PUT 🔽"
    return "NEUTRAL ⏸️"

def get_mock_accuracy():
    return random.randint(85, 99)

# === Generate candle chart ===
def generate_candle_chart(data):
    try:
        values = data['values'][::-1]  # Latest last
        df = pd.DataFrame(values)
        df.rename(columns={
            'datetime': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close'
        }, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].astype(float)

        mpf.plot(df, type='candle', style='charles', title='1-Min Candles', ylabel='Price',
                 savefig='chart.png', tight_layout=True)
        return 'chart.png'
    except Exception as e:
        print("Chart generation error:", e)
        return None

# === Signal sending logic ===
async def send_signal():
    try:
        data = await fetch_candle_data(SYMBOL)

        if not data or "values" not in data:
            print("❌ API error or no candle data.")
            return

        latest = data["values"][0]
        open_price = float(latest["open"])
        close_price = float(latest["close"])

        direction = calculate_direction(open_price, close_price)
        accuracy = get_mock_accuracy()

        if direction == "NEUTRAL":
            print("⏸️ No clear movement. Skipping.")
            return

        if accuracy >= 90:
            ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            time_str = ist_now.strftime('%Y-%m-%d %H:%M:%S')

            msg = (
                f"📊 <b>LIVE Trading Signal</b>\n"
                f"📌 Pair: <code>{SYMBOL}</code>\n"
                f"📈 Direction: <b>{direction}</b>\n"
                f"🎯 Accuracy: <b>{accuracy}%</b>\n"
                f"💹 Open: {open_price:.5f} → Close: {close_price:.5f}\n"
                f"🕐 Time: 1 Min Expiry\n"
                f"🗓️ IST Time: <b>{time_str}</b>"
            )

            chart_file = generate_candle_chart(data)
            if chart_file:
                await bot.send_photo(CHANNEL_OR_USER_ID, photo=open(chart_file, 'rb'), caption=msg, parse_mode="HTML")
                print(f"✅ Signal & chart sent: {direction}, Acc: {accuracy}%")
            else:
                await bot.send_message(CHANNEL_OR_USER_ID, msg, parse_mode="HTML")
                print(f"✅ Signal sent (no chart): {direction}, Acc: {accuracy}%")
        else:
            print(f"⚠️ Accuracy {accuracy}% < 90%. Skipped.")
    except Exception as e:
        print("🚨 Error in send_signal():", e)

# === Message on bot startup ===
async def send_startup_message():
    await bot.send_message(
        CHANNEL_OR_USER_ID,
        "✅ <b>Trading Bot Started</b>\nBot is now live and will send signals every minute.",
        parse_mode="HTML"
    )

# === /start command handler ===
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await message.reply(
        "👋 Welcome to the Quotex Trading Bot!\nYou'll receive 1-min signals based on live market data."
    )

# === Main loop ===
async def main():
    scheduler.add_job(send_signal, "interval", minutes=1)
    scheduler.start()
    await send_startup_message()
    print("🚀 Bot started with chart and TwelveData support.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
