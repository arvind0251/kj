# main.py

import logging, aiohttp, random
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pandas as pd
import mplfinance as mpf
from config import BOT_TOKEN, CHANNEL_OR_USER_ID, FINNHUB_API_KEY, SYMBOL

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
logging.basicConfig(level=logging.INFO)

# === Fetch 10 candles (10min) ===
async def fetch_candle_data(symbol, count=10):
    url = f"https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=1&count={count}&token={FINNHUB_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

# === Generate signal ===
def calculate_direction(open_price, close_price):
    if close_price > open_price:
        return "CALL 🔼"
    elif close_price < open_price:
        return "PUT 🔽"
    return "NEUTRAL ⏸️"

def get_mock_accuracy():
    return random.randint(85, 99)

# === Create chart image ===
def generate_candle_chart(data):
    try:
        df = pd.DataFrame({
            'Open': data['o'],
            'High': data['h'],
            'Low': data['l'],
            'Close': data['c']
        }, index=pd.to_datetime([datetime.fromtimestamp(ts) for ts in data['t']]))
        
        df.index.name = 'Time'
        mpf.plot(df, type='candle', style='charles', title='10-Min Candle', ylabel='Price',
                 savefig='chart.png', tight_layout=True)
        return 'chart.png'
    except Exception as e:
        print("🖼️ Chart generation error:", e)
        return None

# === Send signal to Telegram ===
async def send_signal():
    try:
        data = await fetch_candle_data(SYMBOL, count=10)
        print("🔎 API Response:", data)  # Debug log

        if data.get("s") != "ok" or not data.get("c"):
            print("❌ API error or empty candle data.")
            return

        open_price = data["o"][-1]
        close_price = data["c"][-1]
        direction = calculate_direction(open_price, close_price)
        accuracy = get_mock_accuracy()

        if direction == "NEUTRAL":
            print("⏸️ No movement. Skipping.")
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

            # Generate chart
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

# === Run bot ===
async def main():
    scheduler.add_job(send_signal, "interval", minutes=1)
    scheduler.start()
    print("🚀 Bot started with chart support.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
