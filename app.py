from flask import Flask, request
import os
import requests
import time

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 4
SOL_MINT = "So11111111111111111111111111111111111111112"


def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Missing Telegram config")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })


@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        transfers = tx.get("tokenTransfers", [])
        sol_spent = 0
        token_mint = None
        buyer = None

        for t in transfers:
            if t.get("mint") == SOL_MINT:
                sol_spent += abs(t.get("tokenAmount", 0))
                buyer = t.get("fromUserAccount")
            else:
                token_mint = t.get("mint")

        if sol_spent >= MIN_SOL and token_mint and buyer:
            msg = (
                "🟢 <b>ALPHA BUY</b>\n\n"
                f"👤 Wallet:\n<code>{buyer}</code>\n\n"
                f"🪙 Token:\n<code>{token_mint}</code>\n\n"
                f"💰 Buy: <b>{round(sol_spent, 2)} SOL</b>"
            )
            send_message(msg)

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
