# 🚀 Trading Signal Agent — Setup Guide
## Lepton Agents Hackathon | Arc Network

---

## 📁 Struktur Project

```
trading-signal-agent/
├── python/
│   ├── signal_agent.py      ← Engine sinyal trading (Python)
│   ├── requirements.txt     ← Python dependencies
│   └── signals.json         ← Log sinyal (auto-generated)
├── node/
│   ├── bridge.js            ← Arc payment bridge (Node.js)
│   ├── package.json         ← Node dependencies
│   ├── .env.example         ← Template environment variables
│   ├── .env                 ← Credentials kamu (JANGAN di-commit!)
│   └── subscribers.json     ← Database subscriber
└── docs/
    └── SETUP.md             ← File ini
```

---

## ⚙️ SETUP — Step by Step

### STEP 1 — Persiapan Wallet Bot

> ⚠️ PENTING: Buat wallet BARU khusus untuk bot ini. JANGAN pakai wallet utama kamu.

1. Buka MetaMask → klik icon akun di atas → **"Add account"**
2. Pilih **"Create a new account"** → beri nama "Trading Bot"
3. Catat alamat wallet baru ini
4. Export private key: Settings → Security → Export Private Key
5. Claim testnet USDC di **faucet.circle.com** untuk wallet baru ini

---

### STEP 2 — Setup Node.js Bridge

Buka terminal, masuk ke folder `node/`:

```bash
cd trading-signal-agent/node
```

Install dependencies:
```bash
npm install
```

Buat file .env dari template:
```bash
cp .env.example .env
```

Edit file `.env` dengan text editor, isi:
```
THIRDWEB_CLIENT_ID=b6ba8196c87a693475fc5416f11bc757
THIRDWEB_SECRET_KEY=isi_secret_key_kamu_yang_full
AGENT_WALLET_PRIVATE_KEY=0x_private_key_wallet_bot_kamu
ARC_RPC_URL=https://rpc.testnet.arc.network
ARC_CHAIN_ID=5042002
PORT=3000
SIGNAL_FEE_USDC=0.01
```

Jalankan bridge:
```bash
npm start
```

Kalau berhasil, kamu akan lihat:
```
🔵 Arc Payment Bridge starting...
💳 Agent wallet: 0x...
💰 Signal fee: 0.01 USDC per subscriber
🚀 Payment Bridge running at http://localhost:3000
```

---

### STEP 3 — Setup Python Agent

Buka terminal BARU (biarkan Node.js tetap jalan), masuk ke folder `python/`:

```bash
cd trading-signal-agent/python
```

Buat virtual environment:
```bash
python -m venv venv
```

Aktifkan virtual environment:
```bash
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Jalankan Python agent:
```bash
python signal_agent.py
```

Kalau berhasil, kamu akan lihat:
```
🚀 Trading Signal Agent starting...
📊 Monitoring: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
⏱️  Scan interval: 300s
──────────────────────────────────────────────────
🔍 Scanning 3 pairs...
🟢 BTCUSDT: BUY (score=7.5) | RSI=35.2 | Price=67234.50
⚪ ETHUSDT: NEUTRAL (score=5.0) | RSI=52.1 | Price=3421.20
🔴 SOLUSDT: SELL (score=3.0) | RSI=71.4 | Price=142.80
✅ Signal published: BTCUSDT BUY (score=7.5)
```

---

### STEP 4 — Test Manual

Test apakah bridge berjalan dengan curl atau browser:

**Cek health:**
```bash
curl http://localhost:3000/health
```

**Lihat subscriber:**
```bash
curl http://localhost:3000/subscribers
```

**Tambah subscriber baru:**
```bash
curl -X POST http://localhost:3000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"wallet": "0xAlamat_Wallet_Subscriber", "name": "Test User"}'
```

**Kirim sinyal test manual:**
```bash
curl -X POST http://localhost:3000/signal \
  -H "Content-Type: application/json" \
  -d '{
    "pair": "BTCUSDT",
    "direction": "BUY",
    "score": 7.5,
    "rsi": 35.2,
    "macd": 0.0023,
    "ma_cross": true,
    "ema200": "ABOVE",
    "adx": 28.5,
    "volume_ok": true,
    "timestamp": "2026-06-24T10:00:00",
    "price": 67234.50
  }'
```

---

## 🎯 Cara Kerja Keseluruhan

```
[Binance API] ──► [Python Agent] ──► [Node.js Bridge] ──► [Arc Testnet]
                       │                     │                    │
                  Hitung RSI/MACD       Kirim USDC          Nanopayment
                  Score 0-10          ke subscriber         0.01 USDC/signal
                  Publish sinyal
```

---

## 🔒 Security Checklist

- [ ] Wallet bot TERPISAH dari wallet utama
- [ ] File `.env` ada di `.gitignore`
- [ ] Private key TIDAK hardcoded di code
- [ ] Hanya testnet USDC yang dipakai (tidak ada dana real)

---

## 📹 Demo Video (untuk Submission)

Rekam layar yang menunjukkan:
1. Terminal Node.js bridge running
2. Terminal Python agent scanning pairs
3. Output sinyal muncul (BUY/SELL/NEUTRAL)
4. Transaction di testnet.arcscan.app (bukti USDC terkirim)

Durasi: 2-3 menit cukup.
