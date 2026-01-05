import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== ENV ==========
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# ========== CONFIG ==========
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDT", "USDt", "USDC", "USDCet"}

# storage: wallet|token -> aggregated data
buffers = {}


# ========== HELPERS ==========
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        },
        timeout=10
    )


def flush_alert(key):
    time.sleep(WINDOW_SECONDS)

    data = buffers.pop(key, None)
    if not data:
        return

    wallet = data["wallet"]
    token = data["token"]
    total_sol = round(data["total"], 2)
    count = data["count"]

    if total_sol < MIN_SOL:
        return

    # ===== alert level =====
    if total_sol >= STRONG_SOL:
        title = "🔥🔥 STRONG BUY"
        subtitle = "⚠️ High conviction accumulation"
    else:
        title = "🟢 BUY DETECTED"
        subtitle = ""

    axiom_link = f"https://axiom.trade/token/{token}"

    message = (
        f"{title}\n\n"
        f"{subtitle}\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: {total_sol} SOL\n"
        f"🧾 Buys count: {count}\n\n"
        f"🔗 Open in Axiom\n{axiom_link}"
    )

    send_telegram(message)


# ========== WEBHOOK ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify({"ok": True})

    for tx in data.get("events", []):
        try:
            wallet = tx.get("signer")
            token = tx.get("tokenMint")
            symbol = tx.get("tokenSymbol", "")
            sol_amount = float(tx.get("nativeAmount", 0))

            # ----- filters -----
            if sol_amount <= 0:
                continue
            if token == SOL_MINT:
                continue
            if symbol in STABLECOINS:
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
            print("Error:", e)

    return jsonify({"ok": True})


# ========== START ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
