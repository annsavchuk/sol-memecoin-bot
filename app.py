import os
import threading
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= ENV =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================= TELEGRAM =================
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False
            },
            timeout=10
        )
        print("Telegram status:", r.status_code)
    except Exception as e:
        print("Telegram error:", e)

# ================= TEST ENDPOINT =================
@app.route("/test", methods=["GET"])
def test():
    send_telegram("✅ TEST: Telegram працює")
    return "ok", 200

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("RAW PAYLOAD:", data)

        if not data:
            return jsonify({"ok": True})

        # ---- NORMALIZE ----
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict):
            events = data.get("events") or data.get("data") or []
        else:
            return jsonify({"ok": True})

        if not events:
            print("No events in payload")
            return jsonify({"ok": True})

        # ---- TEMP: просто надсилаємо факт ----
        send_telegram(f"📩 Webhook received: {len(events)} events")

    except Exception as e:
        print("Webhook error:", e)

    return jsonify({"ok": True})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
