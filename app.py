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
MULTI_LIFETIME = 21600  # 6 год
SOL_MINT = "So11111111111111111111111111111111111111112"

# фейкові / непотрібні
STABLE_HINTS = {"usdc", "usdt", "usd", "dai", "busd"}

multi_tokens = {}  # mint -> cluster

# ================== TELEGRAM ==================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        },
        timeout=10
    )

# ================== TOKEN INFO ==================
def fetch_token_info(mint):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        r = requests.get(url, timeout=8).json()
        pairs = r.get("pairs")
        if not pairs:
            return mint[:6], "N/A", None

        p = pairs[0]

        symbol = p["baseToken"].get("symbol", mint[:6])
        name = p["baseToken"].get("name", "")
        text_check = f"{symbol}{name}".lower()

        for bad in STABLE_HINTS:
            if bad in text_check:
                return None, None, None

        fdv = p.get("fdv")
        mc = f"${float(fdv)/1000:.2f}K" if fdv else "N/A"

        pair_address = p.get("pairAddress")
        axiom = None
        if pair_address:
            axiom = f"https://axiom.trade/meme/{pair_address}?chain=sol"

        return symbol, mc, axiom
    except:
        return mint[:6], "N/A", None

# ================== FORMAT BUY ==================
def format_buy(symbol, wallet, sol, mc, axiom):
    text = f"🟢 BUY {symbol}\n\n"
    text += f"👛 {wallet[:6]}...{wallet[-4:]}\n"
    text += f"💰 {sol:.2f} SOL\n\n"
    text += f"MC: {mc}\n"
    if axiom:
        text += axiom
    return text

# ================== FORMAT MULTI ==================
def format_multi(mint, data):
    symbol, mc, axiom = fetch_token_info(mint)
    if not symbol:
        return None

    text = f"‼️ 🟢 MULTI BUY {symbol}\nMulti preset 1\n\n"
    text += f"{len(data['wallets'])} wallets bought {symbol}!\n"
    text += f"Total: {data['total']:.2f} SOL\n\n"

    for w in list(data["wallets"])[-3:]:
        text += f"🔹 {w[:4]}...{w[-4:]}\n"
        text += f"└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    seen = int(time.time() - data["first_seen"])
    text += f"\n🔗 #{symbol} | MC: {mc} | Seen: {seen}s\n"
    if axiom:
        text += axiom
    return text

# ================== WEBHOOK ==================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"ok": True})

    now = time.time()

    for tx in data:
        try:
            wallet = tx.get("feePayer")
            token_transfers = tx.get("tokenTransfers", [])
            if not wallet or not token_transfers:
                continue

            # -------- SOL SPENT --------
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
                if not mint or mint == SOL_MINT:
                    continue

                symbol, mc, axiom = fetch_token_info(mint)
                if not symbol:
                    continue

                cluster = multi_tokens.get(mint)

                if not cluster or now - cluster["first_seen"] > MULTI_LIFETIME:
                    multi_tokens[mint] = {
                        "wallets": {wallet},
                        "per_wallet": {wallet: sol_amount},
                        "total": sol_amount,
                        "first_seen": now
                    }

                    send_telegram(format_buy(symbol, wallet, sol_amount, mc, axiom))

                else:
                    if wallet not in cluster["wallets"]:
                        cluster["wallets"].add(wallet)
                        cluster["per_wallet"][wallet] = sol_amount
                        cluster["total"] += sol_amount

                        if len(cluster["wallets"]) >= 2:
                            msg = format_multi(mint, cluster)
                            if msg:
                                send_telegram(msg)

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
