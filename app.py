import os
import threading
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDC", "USDT", "DAI"}

FLUSH_DELAY = 20  # секунд

buffers = {}

# ====== TELEGRAM ======
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# ====== FLUSH BUFFER ======
def flush_alert(key):
    time.sleep(FLUSH_DELAY)

    data = buffers.get(key)
    if not data:
        return

    wallet = data["wallet"]
    token = data["token"]
    total = round(data["total"], 3)
    count = data["count"]

    text = (
        "🔥 <b>STRONG BUY</b>\n"
        "⚠️ High conviction accumulation\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: <b>{total} SOL</b>\n"
        f"🧾 Buys count: <b>{count}</b>\n\n"
        f"🔗 https://axiom.trade/token/{token}"
    )

    send_telegram(text)

    buffers.pop(key, None)

# ====== WEBHOOK ======
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"ok": True})

    # ---- NORMALIZE PAYLOAD ----
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events") or data.get("data") or []
    else:
        return jsonify({"ok": True})

    if not isinstance(events, list):
        return jsonify({"ok": True})

    for tx in events:
        try:
            if not isinstance(tx, dict):
                continue

            wallet = tx.get("signer") or tx.get("wallet")
            token = tx.get("tokenMint") or tx.get("mint")
            symbol = tx.get("tokenSymbol") or tx.get("symbol")

            raw_amount = tx.get("nativeAmount") or tx.get("amount")
            if raw_amount is None:
                continue

            try:
                sol_amount = float(raw_amount)
            except:
                continue

            # -------- FILTERS --------
            if sol_amount <= 0:
                continue

            # ❌ не реагуємо на SOL
            if token == SOL_MINT or symbol == "SOL":
                continue

            # ❌ не реагуємо на стейбли
            if symbol in STABLECOINS:
                continue

            if not wallet or not token:
                continue

            # -------- BUFFER --------
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

# ====== HEALTHCHECK ======
@app.route("/", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
