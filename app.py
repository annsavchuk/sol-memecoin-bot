import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_TX_SOL = 9
MULTI_LIFETIME = 21600  # 6 год
SOL_MINT = "So11111111111111111111111111111111111111112"

multi_tokens = {}

# ================= TELEGRAM =================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": False
    })

# ================= TOKEN INFO =================
def fetch_token_info(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=8).json()
        pairs = r.get("pairs")
        if not pairs:
            return mint[:6], "N/A", None

        p = pairs[0]
        symbol = p["baseToken"]["symbol"]
        mc = f"${float(p['fdv'])/1000:.2f}K" if p.get("fdv") else "N/A"
        pair = p["pairAddress"]

        link = f"https://axiom.trade/meme/{pair}?chain=sol"
        return symbol, mc, link
    except:
        return mint[:6], "N/A", None

# ================= FORMAT =================
def format_buy(wallet, mint, sol):
    symbol, mc, link = fetch_token_info(mint)
    text = f"🟢 BUY {symbol}\n\n"
    text += f"👛 {wallet[:6]}...{wallet[-4:]}\n"
    text += f"💰 {sol:.2f} SOL\n\n"
    text += f"🔗 MC: {mc}\n"
    if link:
        text += link
    return text

def format_multi(mint, data):
    symbol, mc, link = fetch_token_info(mint)

    text = f"‼️ 🟢 MULTI BUY {symbol}\nMulti preset 1\n\n"
    text += f"{len(data['wallets'])} wallets bought {symbol} in the last 6 hours!\n"
    text += f"Total: {data['total']:.2f} SOL\n\n"

    for w in data["wallets"]:
        text += f"🔹 {w[:4]}...{w[-4:]}\n"
        text += f"└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    seen = int(time.time() - data["first_seen"])
    text += f"\n🔗 #{symbol} | MC: {mc} | Seen: {seen}s\n"
    if link:
        text += link
    return text

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"ok": True})

    now = time.time()

    for tx in data:
        wallet = tx.get("feePayer")
        if not wallet:
            continue

        # SOL SPENT
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

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if not mint or mint == SOL_MINT:
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

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
