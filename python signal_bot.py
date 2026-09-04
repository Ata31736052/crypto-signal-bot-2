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
    # RSI
    df["rsi"] = ta.rsi(df["close"], length=RSI_PERIOD)
    
    # MACD
    macd = ta.macd(df["close"])
    df = pd.concat([df, macd], axis=1)
    
    # EMA 9 و EMA 21
    df["ema9"] = ta.ema(df["close"], length=9)
    df["ema21"] = ta.ema(df["close"], length=21)
    
    # EMA 50 و EMA 200 (برای استراتژی طلایی/مرگ)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)
    
    # TSI
    tsi = ta.tsi(df["close"], fast=13, slow=25)
    df["tsi"] = tsi if tsi is not None else 0
    
    # حجم متوسط
    df["avg_volume"] = df["volume"].rolling(window=14).mean()
    df["volume_ratio"] = df["volume"] / df["avg_volume"]
    
    # مومنتوم
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

def detect_candlestick_patterns(df):
    """تشخیص الگوهای کندل‌شناسی"""
    patterns = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # چکش (Hammer) - خرید
    if (last["high"] - last["low"]) > 0:
        body = abs(last["close"] - last["open"])
        lower_shadow = min(last["open"], last["close"]) - last["low"]
        upper_shadow = last["high"] - max(last["open"], last["close"])
        
        if lower_shadow > 2 * body and upper_shadow < body * 0.3:
            patterns.append("🔨 چکش (خرید)")
    
    # ستاره ثاقب (Shooting Star) - فروش
    if (last["high"] - last["low"]) > 0:
        body = abs(last["close"] - last["open"])
        lower_shadow = min(last["open"], last["close"]) - last["low"]
        upper_shadow = last["high"] - max(last["open"], last["close"])
        
        if upper_shadow > 2 * body and lower_shadow < body * 0.3:
            patterns.append("🌠 ستاره ثاقب (فروش)")
    
    # پوشای صعودی (Bullish Engulfing) - خرید
    if (last["close"] > last["open"] and 
        prev["close"] < prev["open"] and
        last["open"] < prev["close"] and 
        last["close"] > prev["open"]):
        patterns.append("📈 پوشای صعودی (خرید)")
    
    # پوشای نزولی (Bearish Engulfing) - فروش
    if (last["close"] < last["open"] and 
        prev["close"] > prev["open"] and
        last["open"] > prev["close"] and 
        last["close"] < prev["open"]):
        patterns.append("📉 پوشای نزولی (فروش)")
    
    return patterns

def check_signal(symbol):
    try:
        df = get_ohlcv(symbol, TIMEFRAME)
        df, buyer_power = calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ========== داده‌های اصلی ==========
        rsi = last["rsi"]
        macd = last["MACD_12_26_9"]
        macd_signal = last["MACDs_12_26_9"]
        macd_hist = last["MACDh_12_26_9"]
        price = last["close"]
        ema9 = last["ema9"]
        ema21 = last["ema21"]
        ema50 = last["ema50"]
        ema200 = last["ema200"]
        tsi = last["tsi"]
        volume_ratio = last["volume_ratio"]
        momentum = last["momentum"]
        
        # ========== نام فارسی ==========
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
        
        # ========== تشخیص الگوهای کندل ==========
        patterns = detect_candlestick_patterns(df)
        pattern_text = "\n".join([f"• {p}" for p in patterns]) if patterns else "• الگوی خاصی شناسایی نشد"
        
        # ========== استراتژی‌های مختلف ==========
        signals = []
        
        # 1. استراتژی RSI + MACD (استراتژی اصلی)
        if rsi < RSI_OVERSOLD and macd > macd_signal and macd_hist > 0:
            signals.append("🟢 RSI/MACD (خرید)")
        if rsi > RSI_OVERBOUGHT and macd < macd_signal and macd_hist < 0:
            signals.append("🔴 RSI/MACD (فروش)")
        
        # 2. استراتژی میانگین متحرک طلایی/مرگ (EMA 50 و 200)
        if prev["ema50"] < prev["ema200"] and ema50 > ema200:
            signals.append("🟡 تقاطع طلایی (Golden Cross - خرید)")
        if prev["ema50"] > prev["ema200"] and ema50 < ema200:
            signals.append("🔵 تقاطع مرگ (Death Cross - فروش)")
        
        # 3. استراتژی شکست مقاومت/حمایت
        if price > ema21 and price > prev["close"] * 1.02:
            signals.append("📈 شکست مقاومت (خرید)")
        if price < ema21 and price < prev["close"] * 0.98:
            signals.append("📉 شکست حمایت (فروش)")
        
        # 4. استراتژی نوسان‌گیری (Swing)
        if rsi < 30 and momentum < -3:
            signals.append("🔄 نوسان‌گیری (خرید در کف)")
        if rsi > 70 and momentum > 3:
            signals.append("🔄 نوسان‌گیری (فروش در سقف)")
        
        # 5. استراتژی انحراف قیمت از EMA
        deviation = (price - ema21) / ema21 * 100
        if deviation > 5:
            signals.append("📊 انحراف مثبت ۵٪ (احتمال برگشت)")
        if deviation < -5:
            signals.append("📊 انحراف منفی ۵٪ (احتمال برگشت)")
        
        # 6. استراتژی حجم بالا
        if volume_ratio > 1.5 and price > ema21:
            signals.append("📊 حجم بالا + روند صعودی")
        if volume_ratio > 1.5 and price < ema21:
            signals.append("📊 حجم بالا + روند نزولی")
        
        # 7. استراتژی قدرت خریداران
        if buyer_power > 60 and rsi < 50:
            signals.append("💪 قدرت خریداران بالا")
        if buyer_power < 40 and rsi > 50:
            signals.append("📉 قدرت فروشندگان بالا")
        
        # ========== ساخت پیام ==========
        if signals:
            signal_type = "🟢 خرید" if any("خرید" in s for s in signals) else "🔴 فروش" if any("فروش" in s for s in signals) else "⚪ ترکیبی"
            sl = price * 0.97 if "خرید" in "".join(signals) else price * 1.03
            tp = price * 1.06 if "خرید" in "".join(signals) else price * 0.94
            
            message = f"""
📊 <b>سیگنال ترکیبی</b>
ارز: <b>{symbol}</b> ({name})
زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
قیمت: {price:.4f} USDT

<b>📈 داده‌های تکنیکال:</b>
• RSI: {rsi:.2f}
• MACD: {macd:.4f} (سیگنال: {macd_signal:.4f})
• TSI: {tsi:.2f}
• EMA9: {ema9:.2f} | EMA21: {ema21:.2f}
• EMA50: {ema50:.2f} | EMA200: {ema200:.2f}
• مومنتوم: {momentum:+.2f}%
• قدرت خریداران: {buyer_power:.1f}%
• نسبت حجم: {volume_ratio:.2f}x
• انحراف از EMA21: {deviation:+.2f}%

<b>🎯 سیگنال‌های شناسایی شده:</b>
{chr(10).join([f"• {s}" for s in signals])}

<b>🔮 الگوهای کندل:</b>
{pattern_text}

<b>🛑 حد ضرر:</b> {sl:.4f}
<b>🎯 حد سود:</b> {tp:.4f}
"""
            send_telegram(message)
            print(f"✅ سیگنال برای {symbol}")
        
    except Exception as e:
        print(f"خطا در {symbol}:", e)

# ========== اجرای اصلی ==========
print("🤖 ربات سیگنال ترکیبی شروع به کار کرد...")
print(f"📊 تعداد ارزها: {len(SYMBOLS)}")
print(f"⏰ تایم‌فریم: {TIMEFRAME}")
print("─" * 40)

send_telegram("🚀 ربات سیگنال ترکیبی با ۷ استراتژی راه‌اندازی شد!")

for symbol in SYMBOLS:
    check_signal(symbol)

print("─" * 40)
print("✅ بررسی تمام شد.")
