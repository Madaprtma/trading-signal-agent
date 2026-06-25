/**
 * Trading Signal Agent — Arc Payment Bridge
 * ==========================================
 * Node.js server yang:
 *  1. Terima sinyal dari Python agent (POST /signal)
 *  2. Kirim notifikasi + USDC nanopayment ke semua subscriber via Arc
 *  3. Endpoint untuk subscribe/unsubscribe
 * 
 * Pakai thirdweb SDK untuk kirim USDC di Arc Testnet
 */

import express from "express";
import { createThirdwebClient, getContract, prepareContractCall, sendTransaction } from "thirdweb";
import { privateKeyToAccount } from "thirdweb/wallets";
import { defineChain } from "thirdweb/chains";
import { readFileSync, writeFileSync } from "fs";
import dotenv from "dotenv";

dotenv.config();

// ─── SETUP ─────────────────────────────────────────────────────────────────────

const app  = express();
app.use(express.json());

// Arc Testnet chain definition
const arcTestnet = defineChain({
  id:   5042002,
  name: "Arc Testnet",
  nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 6 },
  rpc:  process.env.ARC_RPC_URL || "https://rpc.testnet.arc.network",
});

// thirdweb client
const client = createThirdwebClient({
  clientId:  process.env.THIRDWEB_CLIENT_ID,
  secretKey: process.env.THIRDWEB_SECRET_KEY,
});

// Agent wallet (yang kirim USDC ke subscriber)
const agentAccount = privateKeyToAccount({
  client,
  privateKey: process.env.AGENT_WALLET_PRIVATE_KEY,
});

// USDC contract address di Arc Testnet
const USDC_ADDRESS = "0x3600000000000000000000000000000000000000";
const SIGNAL_FEE   = process.env.SIGNAL_FEE_USDC || "0.01";

console.log("🔵 Arc Payment Bridge starting...");
console.log(`💳 Agent wallet: ${agentAccount.address}`);
console.log(`💰 Signal fee: ${SIGNAL_FEE} USDC per subscriber`);

// ─── HELPER: Load / Save Subscribers ───────────────────────────────────────────

function loadSubscribers() {
  try {
    const data = readFileSync("./subscribers.json", "utf8");
    return JSON.parse(data).subscribers;
  } catch {
    return [];
  }
}

function saveSubscribers(subscribers) {
  writeFileSync("./subscribers.json", JSON.stringify({ subscribers }, null, 2));
}

// ─── HELPER: Send USDC via Arc ──────────────────────────────────────────────────

async function sendUSDC(toAddress, amount) {
  try {
    // Convert USDC amount ke smallest unit (6 decimals)
    const amountInUnits = BigInt(Math.round(parseFloat(amount) * 1_000_000));

    // Get USDC contract
    const usdcContract = getContract({
      client,
      chain: arcTestnet,
      address: USDC_ADDRESS,
    });

    // Prepare transfer transaction
    const transaction = prepareContractCall({
      contract: usdcContract,
      method: "function transfer(address to, uint256 amount) returns (bool)",
      params: [toAddress, amountInUnits],
    });

    // Send transaction
    const result = await sendTransaction({
      account: agentAccount,
      transaction,
    });

    console.log(`✅ Sent ${amount} USDC to ${toAddress} | txHash: ${result.transactionHash}`);
    return { success: true, txHash: result.transactionHash };

  } catch (error) {
    console.error(`❌ Failed to send USDC to ${toAddress}:`, error.message);
    return { success: false, error: error.message };
  }
}

// ─── HELPER: Format Signal Message ─────────────────────────────────────────────

function formatSignalMessage(signal) {
  const emoji = signal.direction === "BUY" ? "🟢" : signal.direction === "SELL" ? "🔴" : "⚪";
  return `
${emoji} TRADING SIGNAL — ${signal.pair}
━━━━━━━━━━━━━━━━━━━━━━
Direction : ${signal.direction}
Score     : ${signal.score}/10
Price     : $${signal.price?.toFixed(2) || "N/A"}
RSI       : ${signal.rsi}
MACD      : ${signal.macd > 0 ? "+" : ""}${signal.macd}
EMA200    : ${signal.ema200}
ADX       : ${signal.adx}
MA Cross  : ${signal.ma_cross ? "Golden ✨" : "Death ☠️"}
Volume    : ${signal.volume_ok ? "High ✅" : "Low ⚠️"}
Time      : ${signal.timestamp}
━━━━━━━━━━━━━━━━━━━━━━
Powered by Arc Network 🔵
  `.trim();
}

// ─── ROUTES ────────────────────────────────────────────────────────────────────

/**
 * POST /signal
 * Endpoint yang dipanggil Python agent setiap ada sinyal baru.
 * Distribusikan ke semua subscriber + kirim USDC nanopayment.
 */
app.post("/signal", async (req, res) => {
  const signal = req.body;

  // Validasi basic
  if (!signal.pair || !signal.direction || signal.score === undefined) {
    return res.status(400).json({ error: "Invalid signal format" });
  }

  console.log(`\n📡 Signal received: ${signal.pair} ${signal.direction} (score=${signal.score})`);

  const subscribers = loadSubscribers().filter(s => s.active);
  console.log(`👥 Distributing to ${subscribers.length} subscriber(s)...`);

  const results = [];

  for (const subscriber of subscribers) {
    console.log(`  → Sending to ${subscriber.name} (${subscriber.wallet})`);

    // Kirim USDC nanopayment
    const paymentResult = await sendUSDC(subscriber.wallet, SIGNAL_FEE);

    results.push({
      subscriber: subscriber.name,
      wallet: subscriber.wallet,
      payment: paymentResult,
      signal_message: formatSignalMessage(signal),
    });

    // Update counter
    subscriber.signals_received = (subscriber.signals_received || 0) + 1;
  }

  // Save updated subscriber data
  const allSubscribers = loadSubscribers();
  saveSubscribers(allSubscribers.map(s => {
    const updated = results.find(r => r.wallet === s.wallet);
    return updated ? { ...s, signals_received: s.signals_received + 1 } : s;
  }));

  console.log(`✅ Signal distributed to ${results.length} subscriber(s)`);

  res.json({
    success: true,
    signal,
    distributed_to: results.length,
    results,
  });
});

/**
 * POST /subscribe
 * Daftarkan wallet baru sebagai subscriber.
 * Body: { wallet: "0x...", name: "nama" }
 */
app.post("/subscribe", (req, res) => {
  const { wallet, name } = req.body;

  if (!wallet || !name) {
    return res.status(400).json({ error: "wallet and name required" });
  }

  const subscribers = loadSubscribers();

  // Cek duplikat
  if (subscribers.find(s => s.wallet.toLowerCase() === wallet.toLowerCase())) {
    return res.status(409).json({ error: "Wallet already subscribed" });
  }

  const newSubscriber = {
    id: `sub_${Date.now()}`,
    wallet,
    name,
    active: true,
    subscribed_at: new Date().toISOString(),
    signals_received: 0,
  };

  subscribers.push(newSubscriber);
  saveSubscribers(subscribers);

  console.log(`➕ New subscriber: ${name} (${wallet})`);
  res.json({ success: true, subscriber: newSubscriber });
});

/**
 * DELETE /unsubscribe
 * Hapus subscriber dari list.
 * Body: { wallet: "0x..." }
 */
app.delete("/unsubscribe", (req, res) => {
  const { wallet } = req.body;
  const subscribers = loadSubscribers();
  const updated = subscribers.filter(s => s.wallet.toLowerCase() !== wallet?.toLowerCase());

  if (updated.length === subscribers.length) {
    return res.status(404).json({ error: "Subscriber not found" });
  }

  saveSubscribers(updated);
  console.log(`➖ Unsubscribed: ${wallet}`);
  res.json({ success: true, message: "Unsubscribed" });
});

/**
 * GET /subscribers
 * Lihat daftar subscriber aktif.
 */
app.get("/subscribers", (req, res) => {
  const subscribers = loadSubscribers();
  res.json({
    total: subscribers.length,
    active: subscribers.filter(s => s.active).length,
    subscribers,
  });
});

/**
 * GET /health
 * Health check endpoint.
 */
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    agent_wallet: agentAccount.address,
    signal_fee: `${SIGNAL_FEE} USDC`,
    chain: "Arc Testnet",
    timestamp: new Date().toISOString(),
  });
});

/**
 * GET /signals/latest
 * Lihat sinyal terbaru dari file log.
 */
app.get("/signals/latest", (req, res) => {
  try {
    const lines = readFileSync("../python/signals.json", "utf8")
      .trim()
      .split("\n")
      .filter(Boolean)
      .map(l => JSON.parse(l))
      .slice(-10); // 10 sinyal terakhir
    res.json({ signals: lines });
  } catch {
    res.json({ signals: [], message: "No signals yet" });
  }
});

// ─── START SERVER ───────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n🚀 Payment Bridge running at http://localhost:${PORT}`);
  console.log(`\nEndpoints:`);
  console.log(`  GET  /health          — status server`);
  console.log(`  GET  /subscribers     — daftar subscriber`);
  console.log(`  POST /signal          — terima sinyal dari Python`);
  console.log(`  POST /subscribe       — daftar subscriber baru`);
  console.log(`  DELETE /unsubscribe   — hapus subscriber`);
  console.log(`  GET  /signals/latest  — sinyal terbaru`);
});
