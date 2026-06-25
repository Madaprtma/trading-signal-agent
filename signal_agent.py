"""
Trading Signal Agent — Lepton Hackathon
========================================
Python agent yang generate sinyal trading dari indikator teknikal,
lalu publish ke Arc via Node.js payment bridge.

Flow:
  1. Fetch OHLCV data dari Binance
  2. Hitung indikator (RSI, MACD, MA, Bollinger, ADX, StochRSI, Volume, EMA200)
  3. Score 0-10 per pair
  4. Publish sinyal ke API bridge (Node.js)
  5. Node.js kirim nanopayment ke subscriber via Arc USDC
"""

import requests
import pandas as pd
import numpy as np
import time
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict

# ─── CONFIG ────────────────────────────────────────────────────────────────────

PAIRS      = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]   # pair yang di-scan
INTERVAL   = "1h"                                  # timeframe
LIMIT      = 100                                   # jumlah candle
SLEEP_SEC  = 60 * 5                               # interval scan (5 menit)
BRIDGE_URL = "http://localhost:3000"               # Node.js payment bridge
SIGNAL_FEE = "0.01"                               # USDC per sinyal ke subscriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── DATA CLASS ────────────────────────────────────────────────────────────────

@dataclass
class Signal:
    pair:       str
    score:      float          # 0-10
    direction:  str            # BUY / SELL / NEUTRAL
    rsi:        float
    macd:       float
    ma_cross:   bool
    ema200:     str            # ABOVE / BELOW
    adx:        float
    volume_ok:  bool
    timestamp:  str
    price:      float

# ─── FETCH DATA ────────────────────────────────────────────────────────────────

def fetch_ohlcv(pair: str, interval: str = INTERVAL, limit: int = LIMIT) -> pd.DataFrame:
    """Fetch OHLCV data dari CoinGecko API (accessible dari Indonesia)."""
    # Map pair ke CoinGecko coin ID
    coin_map = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum", 
        "SOLUSDT": "solana",
        "BNBUSDT": "binancecoin",
        "ADAUSDT": "cardano",
    }
    
    # Map interval ke hari
    days_map = {"1h": 2, "4h": 7, "1d": 30}
    days = days_map.get(interval, 2)
    
    coin_id = coin_map.get(pair)
    if not coin_id:
        log.error(f"Pair {pair} tidak ada di coin_map")
        return pd.DataFrame()
    
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "1"}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            log.error(f"Data kosong untuk {pair}")
            return pd.DataFrame()
        
        # CoinGecko OHLC: [timestamp, open, high, low, close]
        df = pd.DataFrame(data, columns=["open_time", "open", "high", "low", "close"])
        
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        
        # Tambah volume dummy (CoinGecko OHLC endpoint tidak include volume)
        df["volume"] = 1000.0
        
        # Ambil limit candle terakhir
        df = df.tail(limit).reset_index(drop=True)
        
        log.info(f"✅ Fetched {len(df)} candles for {pair} from CoinGecko")
        return df
        
    except Exception as e:
        log.error(f"Gagal fetch {pair}: {e}")
        return pd.DataFrame()
    """Fetch candlestick data dari Bybit API (accessible dari Indonesia)."""
    # Convert pair format: BTCUSDT → BTCUSDT (Bybit pakai format sama)
    # Convert interval: 1h → 60 (Bybit pakai menit)
    interval_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": "D"}
    bybit_interval = interval_map.get(interval, 60)
    
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": pair,
        "interval": bybit_interval,
        "limit": limit
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data["retCode"] != 0:
            log.error(f"Bybit error {pair}: {data['retMsg']}")
            return pd.DataFrame()
        
        # Bybit returns: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
        rows = data["result"]["list"]
        df = pd.DataFrame(rows, columns=[
            "open_time", "open", "high", "low", "close", "volume", "turnover"
        ])
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        
        # Bybit returns newest first, reverse untuk cronologis
        df = df.iloc[::-1].reset_index(drop=True)
        
        return df
    except Exception as e:
        log.error(f"Gagal fetch {pair}: {e}")
        return pd.DataFrame()

# ─── INDIKATOR ─────────────────────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def calc_macd(close: pd.Series) -> float:
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return round(float(hist.iloc[-1]), 4)

def calc_ma_cross(close: pd.Series) -> bool:
    """True = golden cross (MA20 > MA50), False = death cross."""
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    return bool(ma20.iloc[-1] > ma50.iloc[-1])

def calc_bollinger(close: pd.Series, period: int = 20) -> str:
    """Returns: UPPER / MIDDLE / LOWER — posisi harga di Bollinger Band."""
    ma   = close.rolling(period).mean()
    std  = close.rolling(period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    price = close.iloc[-1]
    
    if price >= upper.iloc[-1]:
        return "UPPER"
    elif price <= lower.iloc[-1]:
        return "LOWER"
    else:
        return "MIDDLE"

def calc_ema200(close: pd.Series) -> str:
    """ABOVE atau BELOW EMA 200."""
    ema200 = close.ewm(span=200, adjust=False).mean()
    return "ABOVE" if close.iloc[-1] > ema200.iloc[-1] else "BELOW"

def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Simplified ADX."""
    tr   = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr  = tr.rolling(period).mean()
    adx  = atr.rolling(period).mean()
    return round(float(adx.iloc[-1]), 2)

def calc_stoch_rsi(close: pd.Series, period: int = 14) -> float:
    rsi = 100 - (100 / (1 + (
        close.diff().where(lambda x: x > 0, 0).rolling(period).mean() /
        (-close.diff().where(lambda x: x < 0, 0)).rolling(period).mean()
    )))
    min_rsi = rsi.rolling(period).min()
    max_rsi = rsi.rolling(period).max()
    stoch_rsi = (rsi - min_rsi) / (max_rsi - min_rsi)
    return round(float(stoch_rsi.iloc[-1]) * 100, 2)

def calc_volume_signal(volume: pd.Series) -> bool:
    """True = volume candle terakhir di atas rata-rata 20 candle."""
    avg = volume.rolling(20).mean()
    return bool(volume.iloc[-1] > avg.iloc[-1])

# ─── SCORING SYSTEM ────────────────────────────────────────────────────────────

def calculate_score(df: pd.DataFrame) -> Signal:
    """
    Sistem scoring 8 indikator (0-10).
    Sama persis dengan bot Binance Futures kamu — konsistensi logic.
    """
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]
    price  = float(close.iloc[-1])
    
    rsi      = calc_rsi(close)
    macd     = calc_macd(close)
    ma_cross = calc_ma_cross(close)
    boll     = calc_bollinger(close)
    ema200   = calc_ema200(close)
    adx      = calc_adx(high, low, close)
    stoch    = calc_stoch_rsi(close)
    vol_ok   = calc_volume_signal(volume)

    # --- Scoring Logic ---
    score = 0.0

    # 1. RSI (max 2 poin)
    if rsi < 30:
        score += 2      # oversold = buy signal kuat
    elif rsi < 40:
        score += 1.5
    elif rsi > 70:
        score -= 1      # overbought = warning

    # 2. MACD Histogram (max 1.5 poin)
    if macd > 0:
        score += 1.5
    elif macd < 0:
        score -= 0.5

    # 3. MA Cross (max 1.5 poin)
    if ma_cross:
        score += 1.5    # golden cross

    # 4. Bollinger (max 1 poin)
    if boll == "LOWER":
        score += 1      # harga di lower band = potential bounce
    elif boll == "UPPER":
        score -= 0.5    # harga di upper band = potential reversal

    # 5. EMA200 (max 1 poin)
    if ema200 == "ABOVE":
        score += 1      # bullish trend jangka panjang

    # 6. ADX (max 1 poin)
    if adx > 25:
        score += 1      # trend kuat = valid signal

    # 7. StochRSI (max 1 poin)
    if stoch < 20:
        score += 1      # oversold
    elif stoch > 80:
        score -= 0.5    # overbought

    # 8. Volume (max 0.5 poin)
    if vol_ok:
        score += 0.5    # volume konfirmasi

    # Clamp ke 0-10
    score = max(0.0, min(10.0, round(score + 3, 1)))  # baseline +3

    # Direction
    if score >= 6.5:
        direction = "BUY"
    elif score <= 3.5:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    return Signal(
        pair      = df.get("pair", "UNKNOWN") if isinstance(df, dict) else "UNKNOWN",
        score     = score,
        direction = direction,
        rsi       = rsi,
        macd      = macd,
        ma_cross  = ma_cross,
        ema200    = ema200,
        adx       = adx,
        volume_ok = vol_ok,
        timestamp = datetime.utcnow().isoformat(),
        price     = price,
    )

# ─── PUBLISH SINYAL ────────────────────────────────────────────────────────────

def publish_signal(signal: Signal) -> bool:
    """
    Kirim sinyal ke Node.js bridge → bridge yang handle Arc USDC payment.
    Endpoint: POST /signal
    """
    try:
        payload = asdict(signal)
        resp = requests.post(
            f"{BRIDGE_URL}/signal",
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            log.info(f"✅ Signal published: {signal.pair} {signal.direction} (score={signal.score})")
            return True
        else:
            log.warning(f"❌ Bridge error {resp.status_code}: {resp.text}")
            return False
    except requests.ConnectionError:
        log.error("❌ Node.js bridge tidak berjalan. Jalankan `node bridge.js` dulu.")
        return False

def publish_to_file(signal: Signal):
    """Fallback: simpan sinyal ke file JSON kalau bridge belum running."""
    with open("signals.json", "a") as f:
        f.write(json.dumps(asdict(signal)) + "\n")
    log.info(f"💾 Signal saved to signals.json: {signal.pair} {signal.direction}")

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────

def run():
    log.info("🚀 Trading Signal Agent starting...")
    log.info(f"📊 Monitoring: {PAIRS}")
    log.info(f"⏱️  Scan interval: {SLEEP_SEC}s")
    
    while True:
        log.info("─" * 50)
        log.info(f"🔍 Scanning {len(PAIRS)} pairs...")
        
        signals = []
        
        for pair in PAIRS:
            df = fetch_ohlcv(pair)
            if df.empty:
                continue
            
            # Tambahkan nama pair ke df untuk reference
            signal = calculate_score(df)
            signal.pair = pair  # assign pair name
            
            signals.append(signal)
            
            # Log ringkasan
            emoji = "🟢" if signal.direction == "BUY" else ("🔴" if signal.direction == "SELL" else "⚪")
            log.info(f"{emoji} {pair}: {signal.direction} (score={signal.score}) | RSI={signal.rsi} | Price={signal.price:.2f}")
        
        # Publish semua sinyal
        for signal in signals:
            published = publish_signal(signal)
            if not published:
                publish_to_file(signal)  # fallback ke file
        
        log.info(f"✅ Scan selesai. Tidur {SLEEP_SEC}s...")
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    run()
