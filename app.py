import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def send_telegram(text):
    try:
        requests.post(
            TELEGRAM_URL,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


@app.route("/", methods=["GET"])
def home():
    return "Helius webhook is running"


@app.route("/", methods=["POST"])
def helius_webhook():
    data = request.get_json(silent=True)

    if not data:
        print("No JSON received")
        return jsonify({"status": "no data"}), 200

    print("RAW EVENT:", data)

    # Helius enhanced webhook завжди приходить як список
    if not isinstance(data, list):
        print("Unexpected format, expected list")
        return jsonify({"status": "ok"}), 200

    for event in data:
        try:
            tx_type = event.get("type")
            if tx_type != "SWAP":
                continue

            wallet = event.get("feePayer")

            swaps = event.get("tokenTransfers", [])
            sol_change = 0.0
            token_mint = None

            for t in swaps:
                # якщо це SOL
                if t.get("mint") == "So11111111111111111111111111111111111111112":
                    sol_change += float(t.get("tokenAmount", 0))

                # якщо це токен (не SOL)
                else:
                    token_mint = t.get("mint")

            # BUY = коли SOL зменшився (витратили SOL)
            if sol_change >= 0:
                continue

            sol_spent = abs(sol_change)

            # 🔔 фільтри
            if sol_spent < 9:
                continue

            level = "🟢 BUY DETECTED"
            if sol_spent >= 20:
                level = "🔥 BIG BUY (20+ SOL)"

            msg = (
                f"{level}\n\n"
                f"👛 Wallet:\n{wallet}\n\n"
                f"🪙 Token:\n{token_mint}\n\n"
                f"💰 Amount: ~{sol_spent:.2f} SOL\n\n"
                f"🔗 Open in Axiom\n"
                f"https://axiom.trade/token/{token_mint}"
            )

            send_telegram(msg)

        except Exception as e:
            print("Error processing event:", e)

    return jsonify({"status": "ok"}), 200


@app.route("/test", methods=["GET"])
def test_alert():
    msg = (
        "🧪 TEST ALERT\n\n"
        "Wallet: TEST_WALLET\n"
        "Token: TEST_TOKEN\n"
        "Amount: 12.5 SOL\n\n"
        "https://axiom.trade/token/TEST_TOKEN"
    )
    send_telegram(msg)
    return "Test alert sent"
