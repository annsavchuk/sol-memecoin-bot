import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========= ENV =========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID env variable")

# ========= CONFIG =========
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDT", "USDC", "USDt", "USDCET"}

buffers = {}

# ========= TELEGRAM =========
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": False},
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)


# ========= ALERT AGG =========
def flush_alert(key):
    time.sleep(WINDOW_SECONDS)

    data = buffers.pop(key, None)
    if not data:
        return

    total = round(data["total"], 2)
    if total < MIN_SOL:
        return

    wallet = data["wallet"]
    token = data["token"]
    count = data["count"]

    if total >= STRONG_SOL:
        title = "🔥🔥 STRONG BUY"
        subtitle = "⚠️ High conviction accumulation"
    else:
        title = "🟢 BUY DETECTED"
        subtitle = ""

    link = f"https://axiom.trade/token/{token}"

    msg = (
        f"{title}\n\n"
        f"{subtitle}\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: {total} SOL\n"
        f"🧾 Buys count: {count}\n\n"
        f"🔗 Open in Axiom\n{link}"
    )

    send_telegram(msg)


# ========= WEBHOOK =========
@app.route("/", methods=["POST"])
def webhook():
    payload = request.json
    if not payload:
        return jsonify({"ok": True})

    # Helius enhanced sends LIST of txs
    txs = payload if isinstance(payload, list) else payload.get("events", [])

    for tx in txs:
        try:
            wallet = tx.get("feePayer")
            sol_change = tx.get("nativeBalanceChange", 0)

            # we only care about SOL spent (buy)
            if sol_change >= 0:
                continue

            sol_amount = abs(sol_change)

            # find token bought
            token = None
            symbol = ""

            for t in tx.get("tokenTransfers", []):
                if t.get("toUserAccount") == wallet:
                    token = t.get("mint")
                    symbol = (t.get("tokenSymbol") or "").upper()
                    break

            if not wallet or not token:
                continue

            # -------- FILTERS --------
            if token == SOL_MINT or symbol == "SOL":
                continue

            if symbol in STABLECOINS:
                continue

            if sol_amount <= 0:
                continue

            # -------- AGGREGATION --------
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


# ========= HEALTH =========
@app.route("/", methods=["GET"])
def health():
    return "OK", 200


# ========= START =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
