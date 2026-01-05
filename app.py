import os
from flask import Flask, request, jsonify
import requests
from decimal import Decimal

app = Flask(__name__)

# ===== ENV =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS = Decimal("1000000000")
MIN_SOL = Decimal("4")

# ===== TELEGRAM =====
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        data = [data]

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        buyer = tx.get("feePayer")
        if not buyer:
            continue

        # --- find bought token ---
        token_mint = None
        for t in tx.get("tokenTransfers", []):
            if t.get("toUserAccount") == buyer and t.get("mint") != SOL_MINT:
                token_mint = t.get("mint")
                break

        if not token_mint:
            continue

        # --- SOL outflow (approximate) ---
        lamports_out = Decimal("0")
        for n in tx.get("nativeTransfers", []):
            if n.get("fromUserAccount") == buyer:
                lamports_out += abs(Decimal(str(n.get("amount", 0))))

        sol_spent = (lamports_out / LAMPORTS).quantize(Decimal("0.01"))

        if sol_spent < MIN_SOL:
            continue

        message = (
            "🟢 <b>BUY DETECTED</b>\n\n"
            f"👛 Wallet: <code>{buyer}</code>\n"
            f"🪙 Token: <code>{token_mint}</code>\n"
            f"💰 Amount: ~{sol_spent} SOL\n\n"
            f"🔗 <a href='https://axiom.trade/token/{token_mint}'>Open in Axiom</a>"
        )

        send_telegram(message)

    return jsonify(ok=True)

@app.route("/", methods=["GET"])
def home():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
