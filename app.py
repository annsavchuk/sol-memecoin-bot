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

FAKE_STABLE = {
    "USD", "USDT", "USDC", "USDt", "USDb", "DAI"
}

multi_tokens = {}  # mint -> cluster

# ================== TELEGRAM ==================
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
            "inline_keyboard": [[
                {"text": "AXIOM", "url": button}
            ]]
        }

    requests.post(url, json=payload, timeout=10)

# ================== TOKEN INFO ==================
def fetch_token_info(mint):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        r = requests.get(url, timeout=8).json()
        pairs = r.get("pairs")
        if not pairs:
            return mint[:6], "N/A", f"https://axiom.trade/token/{mint}", mint

        p = pairs[0]
        symbol = p["baseToken"]["symbol"]

        if symbol.upper() in FAKE_STABLE:
            return None, None, None, None

        mc = "N/A"
        if p.get("fdv"):
            mc = f"${float(p['fdv'])/1000:.2f}K"

        pair = p.get("pairAddress")
        if pair:
            link = f"https://axiom.trade/meme/{pair}?chain=sol"
        else:
            link = f"https://axiom.trade/token/{mint}"

        return symbol, mc, link, mint
    except:
        return mint[:6], "N/A", f"https://axiom.trade/token/{mint}", mint

# ================== FORMAT ==================
def format_buy(symbol, wallet, sol, mc, link, mint):
    return (
        f"🟢 <b>BUY {symbol}</b>\n\n"
        f"👛 {wallet[:6]}...{wallet[-4:]}\n"
        f"💰 {sol:.2f} SOL\n\n"
        f"🔗 MC: {mc}\n"
        f"<code>{mint}</code>"
    ), link

def format_multi(mint, data):
    symbol, mc, link, addr = fetch_token_info(mint)
    if not symbol:
        return None, None

    text = (
        f"‼️ 🟢 <b>MULTI BUY {symbol}</b>\n"
        f"Multi preset 1\n\n"
        f"{len(data['wallets'])} wallets bought {symbol} in the last 6 hours!\n"
        f"Total: {data['total']:.2f} SOL\n\n"
    )

    for w in list(data["wallets"])[-5:]:
        text += f"🔹 {w[:4]}...{w[-4:]}\n"
        text += f"└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    seen = int(time.time() - data["first_seen"])
    text += (
        f"\n🔗 #{symbol} | MC: {mc} | Seen: {seen}s\n"
        f"<code>{addr}</code>"
    )
    return text, link

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
            if mint == SOL_MINT:
                continue

            symbol, mc, link, addr = fetch_token_info(mint)
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

                msg, btn = format_buy(symbol, wallet, sol_amount, mc, link, addr)
                send_telegram(msg, btn)

            else:
                if wallet not in cluster["wallets"]:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = sol_amount
                    cluster["total"] += sol_amount

                    if len(cluster["wallets"]) >= 2:
                        msg, btn = format_multi(mint, cluster)
                        if msg:
                            send_telegram(msg, btn)

    return jsonify({"ok": True})

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
