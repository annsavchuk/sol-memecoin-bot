from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

# ===== ENV VARIABLES =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


# ===== TELEGRAM =====
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM_BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


# ===== HEALTH CHECK =====
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    print("\n===== RAW PAYLOAD FROM HELIUS =====")
    print(json.dumps(data, indent=2))
    print("==================================\n")

    send_message("🟢 Webhook received from Helius")

    return "ok", 200


# ===== START SERVER =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
