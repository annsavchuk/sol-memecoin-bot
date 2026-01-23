import os, time, requests
from flask import Flask, request, jsonify
from collections import defaultdict

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_TX_SOL = 5
MULTI_LIFETIME = 21600
WALLET_MERGE_WINDOW = 60  # 60 секунд
SOL_MINT = "So11111111111111111111111111111111111111112"

STABLE_FILTER = ["USD", "USDT", "USDC", "DAI"]

multi_tokens = {}
wallet_clusters = defaultdict(dict)  # mint -> wallet -> cluster

# ===== TELEGRAM =====
def send_telegram(text, button=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if button:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "AXIOM", "url": button}]]
        }
    requests.post(url, json=payload, timeout=10)

# ===== DEX =====
def fetch_pair(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=10).json()
        for p in r.get("pairs", []):
            if p.get("chainId") == "solana":
                return p
    except:
        pass
    return None

def token_info(mint):
    pair = fetch_pair(mint)
    if not pair:
        return mint[:6], "N/A", None, mint

    symbol = pair["baseToken"]["symbol"]
    if any(x in symbol.upper() for x in STABLE_FILTER):
        return None, None, None, None

    mc = pair.get("fdv")
    mc = f"${mc/1000:.2f}K" if mc else "N/A"
    pair_id = pair.get("pairAddress")
    axiom = f"https://axiom.trade/meme/{pair_id}?chain=sol" if pair_id else None
    return symbol, mc, axiom, mint

# ===== FORMAT =====
def format_buy(symbol, wallet, sol, mc, txs, secs, mint):
    return f"""🟢 <b>BUY {symbol}</b>

👛 {wallet[:6]}...{wallet[-4:]}
💰 {sol:.2f} SOL
🔁 ({txs} tx in {secs}s)
📊 MC: {mc}

{mint}"""

def format_multi(symbol, data, mc, mint):
    txt = f"""‼️ 🟢 <b>MULTI BUY {symbol}</b>
Multi preset 1

{len(data['wallets'])} wallets bought {symbol}!
Total: {data['total']:.2f} SOL

"""
    for w in list(data["wallets"])[-5:]:
        txt += f"🔹 {w[:4]}...{w[-4:]}\n└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    seen = int(time.time() - data["first_seen"])
    txt += f"\n#{symbol} | MC: {mc} | Seen: {seen}s\n{mint}"
    return txt

# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    txs = request.json
    if not isinstance(txs, list):
        return jsonify({"ok": True})

    now = time.time()

    for tx in txs:
        wallet = tx.get("feePayer")
        if not wallet: continue

        sol_spent = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet and acc.get("nativeBalanceChange", 0) < 0:
                sol_spent = abs(acc["nativeBalanceChange"])
                break

        sol_amount = sol_spent / 1e9
        if sol_amount < MIN_TX_SOL:
            continue

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint == SOL_MINT: continue

            symbol, mc, axiom, mint_addr = token_info(mint)
            if not symbol:
                continue

            # ---- wallet merge ----
            wc = wallet_clusters[mint].get(wallet)
            if wc and now - wc["last"] <= WALLET_MERGE_WINDOW:
                wc["sum"] += sol_amount
                wc["txs"] += 1
                wc["last"] = now
                continue
            else:
                wallet_clusters[mint][wallet] = {
                    "sum": sol_amount,
                    "txs": 1,
                    "start": now,
                    "last": now
                }
                send_telegram(
                    format_buy(symbol, wallet, sol_amount, mc, 1, 0, mint_addr),
                    axiom
                )

            # ---- MULTI ----
            cluster = multi_tokens.get(mint)
            if not cluster or now - cluster["first_seen"] > MULTI_LIFETIME:
                multi_tokens[mint] = {
                    "wallets": {wallet},
                    "per_wallet": {wallet: sol_amount},
                    "total": sol_amount,
                    "first_seen": now
                }
            else:
                if wallet not in cluster["wallets"]:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = sol_amount
                    cluster["total"] += sol_amount

                    if len(cluster["wallets"]) >= 2:
                        send_telegram(format_multi(symbol, cluster, mc, mint_addr), axiom)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
