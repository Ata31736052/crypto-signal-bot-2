import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import ccxt
import os

# ======== تنظیمات تلگرام ========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ================================

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
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"خطا در ارسال: {response.text}")
    except Exception as e:
        print("خطا در ارسال تلگرام:", e)

def get_ohlcv(symbol, timeframe="4h", limit=100):
    exchange = ccxt.binance({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def calculate_indicators(df):
    # RSI
    df["rsi"] = ta.rsi(df["close"], length=RSI_PERIOD)
    
    # MACD
    macd = ta.macd(df["close"])
    df = pd.concat([df, macd], axis=1)
    
    # EMA 9 و EMA 21
    df["ema9"] = ta.ema(df["close"], length=9)
    df["ema21"] = ta.ema(df["close"], length=21)
    
    # TSI (True Strength Index)
    tsi = ta.tsi(df["close"], fast=13, slow=25)
    df["tsi"] = tsi if tsi is not None else 0
    
    # حجم متوسط 14 کندل
    df["avg_volume"] = df["volume"].rolling(window=14).mean()
    df["volume_ratio"] = df["volume"] / df["avg_volume"]  # نسبت حجم به میانگین
    
    # مومنتوم قیمت (تغییر 4 کندل اخیر)
    df["momentum"] = df["close"].pct_change(periods=4) * 100
    
    # قدرت خریداران
    df["is_green"] = df["close"] > df["open"]
    df["buy_volume"] = df["volume"].where(df["is_green"], 0)
    df["sell_volume"] = df["volume"].where(~df["is_green"], 0)
    
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
        prev = df.iloc[-2]  # کندل قبلی برای مقایسه

        rsi = last["rsi"]
        macd = last["MACD_12_26_9"]
        macd_signal = last["MACDs_12_26_9"]
        macd_hist = last["MACDh_12_26_9"]
        price = last["close"]
        ema9 = last["ema9"]
        ema21 = last["ema21"]
        tsi = last["tsi"]
        volume_ratio = last["volume_ratio"]
        momentum = last["momentum"]
        
        # نام فارسی ارزها
        persian_names = {
            "BTC/USDT": "بیت‌کوین",
            "ETH/USDT": "اتریوم",
            "BNB/USDT": "بایننس کوین",
            "SOL/USDT": "سولانا",
            "SUI/USDT": "سوی",
            "INJ/USDT": "اینکشن",
            "TON/USDT": "گرام (TON)",
            "TRX/USDT": "ترون",
            "ADA/USDT": "کاردانو",
            "XRP/USDT": "ریپل",
            "ZEC/USDT": "زیکش",
            "DOGE/USDT": "دوج‌کوین",
            "AVAX/USDT": "آوالانچ",
            "LINK/USDT": "چین‌لینک",
            "DOT/USDT": "پولکادات"
        }
        name = persian_names.get(symbol, symbol)

        # ========== شرایط سیگنال خرید ==========
        long_entry = (
            rsi < RSI_OVERSOLD and
            macd > macd_signal and
            macd_hist > 0 and
            buyer_power > 55 and
            ema9 > ema21 and          # روند صعودی کوتاه‌مدت
            tsi > -20 and             # TSI بالای -20
            volume_ratio > 1.2 and    # حجم بالاتر از میانگین
            price > ema21             # قیمت بالای EMA21
        )

        # ========== شرایط سیگنال فروش ==========
        short_entry = (
            rsi > RSI_OVERBOUGHT and
            macd < macd_signal and
            macd_hist < 0 and
            buyer_power < 45 and
            ema9 < ema21 and          # روند نزولی کوتاه‌مدت
            tsi < 20 and              # TSI زیر 20
            volume_ratio > 1.2 and    # حجم بالاتر از میانگین
            price < ema21             # قیمت زیر EMA21
        )

        # ========== ساخت پیام ==========
        def build_message(signal_type, sl, tp):
            if symbol == "TON/USDT":
                sl_gram = sl * 1
                tp_gram = tp * 1
                gram_text = f"\n📊 معادل TON: {sl_gram:.2f} (ضرر) | {tp_gram:.2f} (سود)"
            else:
                gram_text = ""

            emoji = "🟢" if signal_type == "خرید" else "🔴"
            trend = "صعودی 📈" if signal_type == "خرید" else "نزولی 📉"
            macd_status = "بالای سیگنال" if signal_type == "خرید" else "زیر سیگنال"

            return f"""
{emoji} <b>سیگنال {signal_type} ({trend})</b>

ارز: <b>{symbol}</b> ({name})
زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
قیمت ورود: {price:.6f} USDT

📊 <b>تحلیل تکنیکال:</b>
• RSI: {rsi:.2f}
• MACD: {macd_status} (تأیید {trend})
• TSI: {tsi:.2f}
• EMA9 / EMA21: {ema9:.2f} / {ema21:.2f}
• مومنتوم (4h): {momentum:+.2f}%
• نسبت حجم: {volume_ratio:.2f}x
• قدرت خریداران: {buyer_power:.1f}%

🛑 حد ضرر: {sl:.6f} USDT
🎯 حد سود: {tp:.6f} USDT
{gram_text}
"""
        if long_entry:
            sl = price * 0.97
            tp = price * 1.06
            message = build_message("خرید", sl, tp)
            send_telegram(message)
            print(f"✅ خرید → {symbol}")

        elif short_entry:
            sl = price * 1.03
            tp = price * 0.94
            message = build_message("فروش", sl, tp)
            send_telegram(message)
            print(f"✅ فروش → {symbol}")

    except Exception as e:
        print(f"خطا در {symbol}:", e)

# ======== اجرای اصلی ========
print("🤖 ربات سیگنال شروع به کار کرد...")
print(f"📊 تعداد ارزها: {len(SYMBOLS)}")
print(f"⏰ تایم‌فریم: {TIMEFRAME}")
print("─" * 40)

send_telegram("🚀 ربات سیگنال با موفقیت راه‌اندازی شد!")

for symbol in SYMBOLS:
    check_signal(symbol)

print("─" * 40)
print("✅ بررسی تمام شد.")
