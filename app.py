from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

# ======================
# ENV VARIABLES
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 4
SOL_MINT = "So11111111111111111111111111111111111111112"

# ======================
# LOAD WALLETS
# ======================
def load_wallets():
    wallets = set()
    try:
        with open("wallets.txt", "r") as f:
            for line in f:
                w = line.strip()
                if w:
                    wallets.add(w)
    except Exception as e:
        print("❌ wallets.txt error:", e)
    print(f"✅ Loaded {len(wallets)} wallets")
    return wallets

TRACKED_WALLETS = load_wallets()

# ======================
# TELEGRAM
# ======================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram:", r.text)
    except Exception as e:
        print("Telegram error:", e)

# ======================
# TEST ENDPOINT
# ======================
@app.route("/", methods=["GET"])
def home():
    send_message("✅ <b>Bot is alive</b>\nRender + Telegram працюють")
    return "Bot is running"

# ======================
# HELIUS WEBHOOK
# ======================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    print("=== WEBHOOK RECEIVED ===")
    print(json.dumps(data, indent=2))

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        tx_type = tx.get("type")

        # Нас цікавить тільки SWAP (покупки)
        if tx_type != "SWAP":
            continue

        transfers = tx.get("tokenTransfers", [])
        if not transfers:
            continue

        for t in transfers:
            mint = t.get("mint")
            amount = t.get("tokenAmount")
            buyer = t.get("toUserAccount")
            seller = t.get("fromUserAccount")

            # тільки SOL
            if mint != SOL_MINT:
                continue

            # мінімум SOL
            if not amount or amount < MIN_SOL:
                continue

            # тільки якщо BUYER у нашому списку
            if buyer not in TRACKED_WALLETS:
                continue

            message = (
                "🚨 <b>BUY ALERT</b>\n\n"
                f"💰 <b>Amount:</b> {round(amount, 2)} SOL\n"
                f"🧠 <b>Buyer:</b>\n<code>{buyer}</code>\n\n"
                f"📤 <b>From:</b>\n<code>{seller}</code>\n\n"
                f"🔁 <b>Type:</b> {tx_type}"
            )

            send_message(message)

    return "ok"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
