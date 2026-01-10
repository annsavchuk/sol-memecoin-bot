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
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID")

# ===== CONFIG =====
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

SOL_MINT = "So11111111111111111111111111111111111111112"

buffers = {}

# ===== TELEGRAM =====
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print("Telegram error:", e)

# ===== FLUSH =====
def flush_alert(key):
    time.sleep(WINDOW_SECONDS)

    data = buffers.pop(key, None)
    if not data:
        return

    total_sol = round(data["total"], 2)
    if total_sol < MIN_SOL:
        return

    wallet = data["wallet"]
    token = data["token"]
    count = data["count"]

    if total_sol >= STRONG_SOL:
        title = "🔥🔥 STRONG BUY"
        subtitle = "⚠️ High conviction accumulation"
    else:
        title = "🟢 BUY DETECTED"
        subtitle = ""

    axiom = f"https://axiom.trade/token/{token}"

    msg = (
        f"{title}\n\n"
        f"{subtitle}\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: {total_sol} SOL\n"
        f"🧾 Buys count: {count}\n\n"
        f"🔗 Open in Axiom\n{axiom}"
    )

    send_telegram(msg)

# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    payload = request.json
    if not payload:
        return jsonify({"ok": True})

    print("Incoming payload:", payload)

    for tx in payload:
        try:
            if tx.get("type") != "SWAP":
                continue

            transfers = tx.get("tokenTransfers", [])
            sol_spent = 0
            bought_token = None
            wallet = None

            for t in transfers:
                amt = t.get("amount")
                if amt is None:
                    continue

                mint = t.get("mint")

                if mint == SOL_MINT and amt < 0:
                    sol_spent += abs(amt) / 1e9

                if mint != SOL_MINT and amt > 0:
                    bought_token = mint
                    wallet = t.get("toUserAccount")

            if not wallet or not bought_token:
                continue

            if sol_spent <= 0:
                continue

            key = f"{wallet}|{bought_token}"

            if key not in buffers:
                buffers[key] = {
                    "wallet": wallet,
                    "token": bought_token,
                    "total": sol_spent,
                    "count": 1
                }
                threading.Thread(target=flush_alert, args=(key,), daemon=True).start()
            else:
                buffers[key]["total"] += sol_spent
                buffers[key]["count"] += 1

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})

# ===== HEALTH =====
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

# ===== START =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
