# Trading Signal Agent
### AI-powered trading signals with Arc Network USDC nanopayments

> Built for **Lepton Agents Hackathon** — Canteen x Circle x Arc Network

---

## 🎯 What It Does

Trading Signal Agent is an autonomous AI agent that:

1. **Scans** BTC, ETH, and SOL markets every 5 minutes using 8 technical indicators
2. **Scores** each asset from 0–10 and generates BUY / SELL / NEUTRAL signals
3. **Pays** every subscriber **0.01 USDC** via Arc Network for each signal received

This demonstrates Arc's core value proposition: **sub-cent stablecoin payments that are actually viable** — something impossible on chains with volatile gas fees.

---

## 🏗️ Architecture

```
┌─────────────────┐     POST /signal      ┌──────────────────┐     Arc Testnet
│  Python Agent   │ ───────────────────►  │  Node.js Bridge  │ ──────────────►
│                 │                        │                  │   0.01 USDC
│  • CoinGecko    │                        │  • thirdweb SDK  │   per signal
│  • 8 indicators │                        │  • Express API   │   to each
│  • Score 0-10   │                        │  • Subscriber DB │   subscriber
└─────────────────┘                        └──────────────────┘
```

### Flow
1. Python agent fetches OHLCV data from CoinGecko API
2. Calculates 8 indicators and generates a score
3. POSTs signal to Node.js bridge at `localhost:3000`
4. Bridge distributes signal + sends **0.01 USDC** to every active subscriber via Arc
5. Transaction is recorded on-chain — verifiable on Arc Testnet explorer

---

## 📊 Signal Scoring System (8 Indicators)

| # | Indicator | Weight | Signal |
|---|-----------|--------|--------|
| 1 | RSI | 2.0 pts | < 30 = oversold (BUY) |
| 2 | MACD Histogram | 1.5 pts | > 0 = bullish |
| 3 | MA Cross (20/50) | 1.5 pts | Golden cross = BUY |
| 4 | Bollinger Bands | 1.0 pts | Lower band = bounce |
| 5 | EMA 200 | 1.0 pts | Price above = bullish |
| 6 | ADX | 1.0 pts | > 25 = strong trend |
| 7 | StochRSI | 1.0 pts | < 20 = oversold |
| 8 | Volume | 0.5 pts | Above avg = confirms |

**Score ≥ 6.5 → BUY | Score ≤ 3.5 → SELL | Otherwise → NEUTRAL**

---

## 💡 Why Arc Network?

Traditional payment rails can't support agent-to-agent micropayments:

| Chain | Gas Cost | Viable for $0.01? |
|-------|----------|-------------------|
| Ethereum | ~$2-20 | ❌ No |
| Polygon | ~$0.01-0.05 | ⚠️ Borderline |
| **Arc Network** | **~$0.0001 USDC** | **✅ Yes** |

Arc's stablecoin-native design (USDC as gas token) makes nanopayments economically viable — enabling entirely new agent economy models where:
- Agents **earn** for providing value (signals, data, computation)
- Agents **pay** for services they consume
- All settlement is **deterministic and sub-second**

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Signal Engine | Python 3.14 + pandas + numpy |
| Market Data | CoinGecko API (no API key needed) |
| Payment Bridge | Node.js + Express |
| Blockchain SDK | thirdweb v5 |
| Chain | Arc Network Testnet (Chain ID: 5042002) |
| Payment Token | USDC (native gas token on Arc) |

---

## 🚀 Quick Start

### Prerequisites
- Node.js v18+
- Python 3.10+
- thirdweb account (free at thirdweb.com)
- Wallet with Arc Testnet USDC (free from faucet.circle.com)

### 1. Clone & Install

```bash
git clone https://github.com/Madaprtma/trading-signal-agent.git
cd trading-signal-agent
npm install
pip install requests pandas numpy
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
THIRDWEB_CLIENT_ID=your_client_id
THIRDWEB_SECRET_KEY=your_secret_key
AGENT_WALLET_PRIVATE_KEY=0x_your_bot_wallet_private_key
ARC_RPC_URL=https://rpc.testnet.arc.network
ARC_CHAIN_ID=5042002
PORT=3000
SIGNAL_FEE_USDC=0.01
```

### 3. Run the Bridge (Terminal 1)

```bash
node bridge.js
```

Output:
```
🔵 Arc Payment Bridge starting...
💳 Agent wallet: 0x018fBE6bB41...
💰 Signal fee: 0.01 USDC per subscriber
🚀 Payment Bridge running at http://localhost:3000
```

### 4. Run the Signal Agent (Terminal 2)

```bash
python signal_agent.py
```

Output:
```
🚀 Trading Signal Agent starting...
📊 Monitoring: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
🟢 BTCUSDT: BUY (score=7.5) | RSI=35.2 | Price=61653.00
✅ Signal published: BTCUSDT BUY (score=7.5)
```

### 5. Subscribe a Wallet

```bash
curl -X POST http://localhost:3000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"wallet": "0xYourWallet", "name": "Your Name"}'
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server status + agent wallet |
| GET | `/subscribers` | List active subscribers |
| POST | `/subscribe` | Add new subscriber |
| DELETE | `/unsubscribe` | Remove subscriber |
| POST | `/signal` | Receive signal + trigger payments |
| GET | `/signals/latest` | Last 10 signals |

---

## 🔍 Live Demo

**Arc Testnet Transactions:**
- Agent Wallet: `0x018fBE6bB41b6bA47AfBC499b60375117A9373ea`
- Sample txHash: `0x3c9a32d2711323392228a72753c4a52b1c75a13b74e20d1016e38d67bf9c323e`
- Explorer: [testnet.arcscan.app](https://testnet.arcscan.app)

---

## 🌐 Expanding the Agent Economy

This project is a foundation. Future extensions:

- **Multi-agent marketplace** — agents subscribe to other agents' signals
- **Performance-based fees** — agents earn more when signals are accurate
- **Cross-chain settlement** — use Arc's CCTP for multi-chain subscriber payments
- **On-chain signal registry** — store signals in a smart contract for auditability
- **Telegram/Discord bot** — push signals to messaging platforms with payment proof

---

## 👤 Builder

**Teerast (Mada Pratama)**
- GitHub: [@Madaprtma](https://github.com/Madaprtma)
- Talent Protocol: [talent.app/madaprtma](https://talent.app/madaprtma)
- Arc Testnet: `0xDfE1eD25BA20e7981AEAe69cDfcfE93509661574`

Independent developer building automated trading infrastructure in Python.
Exploring how Arc's stablecoin-native architecture can power the next generation of autonomous financial agents.

---

## 📄 License

MIT — feel free to fork and build on top of this.

---

*Built with ❤️ on Arc Network Testnet | Lepton Agents Hackathon 2026*
