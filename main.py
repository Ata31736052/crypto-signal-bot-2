import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import ccxt
import os

TELEGRAM_BOT_TOKEN = os.getenv("8838013512:AAEMkDpCnzIU-VEnPp30bjLNRTXowz8Al4I")
TELEGRAM_CHAT_ID = os.getenv("90464197")

SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "SUI/USDT",
    "INJ/USDT", "TON/USDT", "TRX/USDT", "ADA/USDT", "XRP/USDT",
    "ZEC/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
]

TIMEFRAME = "4h"
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("خطا در ارسال تلگرام:", e)

def get_ohlcv(symbol, timeframe="4h", limit=100):
    exchange = ccxt.binance({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def calculate_indicators(df):
    df["rsi"] = ta.rsi(df["close"], length=RSI_PERIOD)
    macd = ta.macd(df["close"])
    df = pd.concat([df, macd], axis=1)

    df["is_green"] = df["close"] > df["open"]
    df["buy_volume"] = df["volume"].where(df["is_green"], 0)
    df["sell_volume"] = df["volume"].where(\~df["is_green"], 0)

    recent = df.tail(20)
    total_buy = recent["buy_volume"].sum()
    total_sell = recent["sell_volume"].sum()
    buyer_power = total_buy / (total_buy + total_sell + 1e-9) * 100
    return df, buyer_power

def check_signal(symbol):
    try:
        df = get_ohlcv(symbol, TIMEFRAME)
        df, buyer_power = calculate_indicators(df)
        last = df.iloc[-1]

        rsi = last["rsi"]
        macd = last["MACD_12_26_9"]
        macd_signal = last["MACDs_12_26_9"]
        macd_hist = last["MACDh_12_26_9"]
        price = last["close"]

        long_entry = (rsi < RSI_OVERSOLD and macd > macd_signal and macd_hist > 0 and buyer_power > 55)
        short_entry = (rsi > RSI_OVERBOUGHT and macd < macd_signal and macd_hist < 0 and buyer_power < 45)

        if long_entry:
            sl = price * 0.97
            tp = price * 1.06
            message = f"""
🟢 <b>سیگنال خرید (کف)</b>

ارز: <b>{symbol}</b>
زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
قیمت ورود: {price:.6f}

📊 RSI: {rsi:.2f}
📈 MACD: تأیید صعودی
💪 قدرت خریداران: {buyer_power:.1f}%

🛑 حد ضرر: {sl:.6f}
🎯 حد سود: {tp:.6f}
"""
            send_telegram(message)
            print(f"✅ خرید → {symbol}")

        elif short_entry:
            sl = price * 1.03
            tp = price * 0.94
            message = f"""
🔴 <b>سیگنال فروش (سقف)</b>

ارز: <b>{symbol}</b>
زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
قیمت ورود: {price:.6f}

📊 RSI: {rsi:.2f}
📉 MACD: تأیید نزولی
💪 قدرت خریداران: {buyer_power:.1f}%

🛑 حد ضرر: {sl:.6f}
🎯 حد سود: {tp:.6f}
"""
            send_telegram(message)
            print(f"✅ فروش → {symbol}")

    except Exception as e:
        print(f"خطا در {symbol}:", e)

print("ربات سیگنال شروع به کار کرد...")
for symbol in SYMBOLS:
    check_signal(symbol)
print("بررسی تمام شد.")
