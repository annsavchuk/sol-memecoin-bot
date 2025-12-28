from flask import Flask, request, jsonify
import os
import requests
import json

app = Flask(__name__)

# ENV VARIABLES
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running 🚀"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    print("=== WEBHOOK RECEIVED ===")
    print(json.dumps(data, indent=2))

    # Helius always sends LIST of transactions
    if not isinstance(data, list):
        return jsonify({"status": "ignored"}), 200

    for tx in data:
        tx_type = tx.get("type")
        token_transfers = tx.get("tokenTransfers", [])

        # Ignore transactions without token transfers
        if not token_transfers:
            continue

        for transfer in token_transfers:
            mint = transfer.get("mint")
            amount = transfer.get("tokenAmount")
            to_wallet = transfer.get("toUserAccount")
            from_wallet = transfer.get("fromUserAccount")

            if not mint or not amount:
                continue

            message = (
                "🟢 <b>Token movement detected</b>\n\n"
                f"🪙 <b>Mint:</b> <code>{mint}</code>\n"
                f"💰 <b>Amount:</b> {amount}\n\n"
                f"📤 <b>From:</b> <code>{from_wallet}</code>\n"
                f"📥 <b>To:</b> <code>{to_wallet}</code>\n\n"
                f"🔁 <b>Type:</b> {tx_type}"
            )

            send_message(message)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
