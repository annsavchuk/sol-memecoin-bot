from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

# =====================
# ENV VARIABLES
# =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 4  # мінімум SOL для алерта
SOL_MINT = "So11111111111111111111111111111111111111112"

# =====================
# TELEGRAM SENDER
# =====================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM_BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram response:", r.text)
    except Exception as e:
        print("Telegram error:", e)

# =====================
# TEST ENDPOINT
# =====================
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

# =====================
# HELIUS WEBHOOK
# =====================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    print("=== WEBHOOK RECEIVED ===")
    print(json.dumps(data, indent=2))

    # Helius надсилає список транзакцій
    if not isinstance(data, list):
        return "ok"

    for tx in data:
        tx_type = tx.get("type")
        token_transfers = tx.get("tokenTransfers", [])

        for transfer in token_transfers:
            mint = transfer.get("mint")
            amount = transfer.get("tokenAmount")
            to_wallet = transfer.get("toUserAccount")
            from_wallet = transfer.get("fromUserAccount")

            # беремо тільки SOL
            if mint != SOL_MINT:
                continue

            if not amount or amount < MIN_SOL:
                continue

            message = (
                "🚨 <b>BUY ALERT</b>\n\n"
                f"💰 <b>Amount:</b> {round(amount, 2)} SOL\n"
                f"📥 <b>Buyer:</b>\n<code>{to_wallet}</code>\n\n"
                f"📤 <b>From:</b>\n<code>{from_wallet}</code>\n\n"
                f"🔁 <b>Type:</b> {tx_type}"
            )

            send_message(message)

    return "ok"

# =====================
# RUN
# =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
