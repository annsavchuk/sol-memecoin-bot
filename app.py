import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== ENV =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID env variable")

# ===== CONFIG =====
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

buffers = {}

# ===== HELPERS =====
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        }, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def flush_alert(key):
    time.sleep(WINDOW_SECONDS)

    data = buffers.pop(key, None)
    if not data:
        return

    total_sol = round(data["total"], 2)
    if total_sol < MIN_SOL:
        print("Skip alert, amount too small:", total_sol)
        return

    wallet = data["wallet"]
    token = data["token"]
    count = data["count"]

    if total_sol >= STRONG_SOL:
        title = "🔥🔥 STRONG BUY"
    else:
        title = "🟢 BUY DETECTED"

    axiom_link = f"https://axiom.trade/token/{token}"

    msg = (
        f"{title}\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: {total_sol} SOL\n"
        f"🧾 Buys count: {count}\n\n"
        f"🔗 Open in Axiom\n{axiom_link}"
    )

    send_telegram(msg)


# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True)
    print("Incoming payload:", data)

    if not data:
        return jsonify({"ok": True})

    events = []

    # підтримка різних форматів
    if isinstance(data, dict):
        events = data.get("events") or data.get("data") or []
    elif isinstance(data, list):
        events = data

    for tx in events:
        try:
            wallet = tx.get("signer") or tx.get("wallet")
            token = tx.get("tokenMint") or tx.get("token")
            sol_amount = (
                tx.get("nativeAmount")
                or tx.get("solAmount")
                or tx.get("amount")
                or 0
            )

            sol_amount = float(sol_amount)

            print("TX:", wallet, token, sol_amount)

            if not wallet or not token:
                continue

            if sol_amount < 0.1:
                continue

            key = f"{wallet}|{token}"

            if key not in buffers:
                buffers[key] = {
                    "wallet": wallet,
                    "token": token,
                    "total": sol_amount,
                    "count": 1
                }
                threading.Thread(
                    target=flush_alert,
                    args=(key,),
                    daemon=True
                ).start()
            else:
                buffers[key]["total"] += sol_amount
                buffers[key]["count"] += 1

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})


# ===== HEALTH + TEST =====
@app.route("/", methods=["GET"])
def health():
    send_telegram(
        "🧪 TEST ALERT\n\n"
        "Wallet: TEST_WALLET_123\n"
        "Token: TEST_TOKEN_ABC\n"
        "Total amount: 12.5 SOL\n"
        "Buys count: 1\n\n"
        "https://axiom.trade/token/TEST_TOKEN_ABC"
    )
    return "Test alert sent", 200


# ===== START =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
