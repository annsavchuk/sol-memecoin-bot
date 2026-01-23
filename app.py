import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================== SETTINGS ==================
MIN_TX_SOL = 9
MULTI_LIFETIME = 21600   # 6 год
SOL_MINT = "So11111111111111111111111111111111111111112"

FAKE_STABLES = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCER7v6t8z8F7hZ9K2p7pVJ5yYjFv4PpU9b",   # USDT
}

multi_tokens = {}  # mint -> cluster

# ================== TELEGRAM ==================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    })

# ================== TOKEN INFO ==================
def fetch_token_info(mint):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        r = requests.get(url, timeout=8).json()
        pairs = r.get("pairs")
        if not pairs:
            return mint[:6], None, f"https://axiom.trade/meme/{mint}?chain=sol"

        p = pairs[0]
        symbol = p["baseToken"]["symbol"]
        mc = f"${float(p['fdv'])/1000:.2f}K" if p.get("fdv") else None
        return symbol, mc, f"https://axiom.trade/meme/{mint}?chain=sol"
    except:
        return mint[:6], None, f"https://axiom.trade/meme/{mint}?chain=sol"

# ================== FORMAT ==================
def format_buy(wallet, mint, sol):
    symbol, mc, link = fetch_token_info(mint)
    text = f"🟢 BUY {symbol}\n\n"
    text += f"👛 {wallet[:6]}...{wallet[-4:]}\n"
    text += f"💰 {sol:.2f} SOL\n"
    if mc:
        text += f"\n🔗 MC: {mc}\n{link}"
    else:
        text += f"\n🔗 {link}"
    return text

def format_multi(mint, data):
    symbol, mc, link = fetch_token_info(mint)

    text = f"‼️ 🟢 MULTI BUY {symbol}\nMulti preset 1\n\n"
    text += f"{len(data['wallets'])} wallets bought {symbol} in the last 6 hours!\n"
    text += f"Total: {data['total']:.2f} SOL\n\n"

    for w in list(data["wallets"])[-5:]:
        text += f"🔹 {w[:4]}...{w[-4:]}\n"
        text += f"└ {data['per_wallet'][w]:.2f} SOL"
        if mc:
            text += f" | MC {mc}"
        text += "\n"

    seen = int(time.time() - data["first_seen"])
    if mc:
        text += f"\n🔗 #{symbol} | MC: {mc} | Seen: {seen}s\n{link}"
    else:
        text += f"\n🔗 #{symbol} | Seen: {seen}s\n{link}"
    return text

# ================== WEBHOOK ==================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"ok": True})

    now = time.time()

    for tx in data:
        wallet = tx.get("feePayer")
        token_transfers = tx.get("tokenTransfers", [])

        if not wallet or not token_transfers:
            continue

        sol_spent = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet:
                change = acc.get("nativeBalanceChange", 0)
                if change < 0:
                    sol_spent = abs(change)
                    break

        sol_amount = sol_spent / 1e9
        if sol_amount < MIN_TX_SOL:
            continue

        for t in token_transfers:
            mint = t.get("mint")
            if mint in FAKE_STABLES or mint == SOL_MINT:
                continue

            cluster = multi_tokens.get(mint)

            if not cluster or now - cluster["first_seen"] > MULTI_LIFETIME:
                multi_tokens[mint] = {
                    "wallets": {wallet},
                    "per_wallet": {wallet: sol_amount},
                    "total": sol_amount,
                    "first_seen": now
                }
                send_telegram(format_buy(wallet, mint, sol_amount))

            else:
                if wallet not in cluster["wallets"]:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = sol_amount
                    cluster["total"] += sol_amount

                    if len(cluster["wallets"]) >= 2:
                        send_telegram(format_multi(mint, cluster))

    return jsonify({"ok": True})

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
