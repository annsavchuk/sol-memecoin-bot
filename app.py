import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= ENV =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID env variable")

# ================= CONFIG =================
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

# SOL filters
SOL_MINTS = {
    "So11111111111111111111111111111111111111112",
    "SOL"
}

# Stablecoins (symbols)
STABLECOINS = {"USDT", "USDC", "USDt", "USDCET"}

# buffer: wallet|token -> data
buffers = {}

# ================= HELPERS =================
def send_telegram(text: str):
    try:
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
    except Exception as e:
        print("Telegram error:", e)


def flush_alert(key: str):
    """Wait WINDOW_SECONDS, then send aggregated alert"""
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

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify({"ok": True})

    # Helius can send:
    # - list of txs
    # - { events: [...] }
    tx_list = data if isinstance(data, list) else data.get("events", [])

    for tx in tx_list:
        try:
            # try multiple possible fields (Helius differs by type)
            wallet = tx.get("signer") or tx.get("feePayer")
            token = tx.get("tokenMint")
            symbol = (tx.get("tokenSymbol") or "").upper()
            sol_amount = float(tx.get("nativeAmount", 0))

            # --------- BASIC VALIDATION ----------
            if not wallet or not token:
                continue

            # --------- FILTERS ----------
            # ignore SOL
            if token in SOL_MINTS or symbol == "SOL":
                continue

            # ignore stablecoins
            if symbol in STABLECOINS:
                continue

            # ignore dust / non-buys
            if sol_amount <= 0:
                continue

            # --------- AGGREGATION ----------
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
            print("TX error:", e)

    return jsonify({"ok": True})


# ================= HEALTH =================
@app.route("/", methods=["GET"])
def health():
    return "OK", 200


# ================= START =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
