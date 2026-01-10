import os
import time
import threading
import requests
from flask import Flask, request, jsonify

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDT", "USDC", "DAI"}

ALERT_DELAY = 30  # секунд
MIN_ALERT_SOL = 9

# ---------------- APP ----------------
app = Flask(__name__)

buffers = {}

# ---------------- TELEGRAM ----------------
def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# ---------------- FLUSH BUFFER ----------------
def flush_alert(key):
    time.sleep(ALERT_DELAY)

    data = buffers.get(key)
    if not data:
        return

    total = data["total"]
    count = data["count"]
    wallet = data["wallet"]
    token = data["token"]

    if total >= MIN_ALERT_SOL:
        msg = (
            f"🔥 <b>STRONG BUY</b>\n\n"
            f"👛 Wallet: <code>{wallet}</code>\n"
            f"🪙 Token: <code>{token}</code>\n\n"
            f"💰 Total amount: <b>{total:.2f} SOL</b>\n"
            f"🧾 Buys count: <b>{count}</b>"
        )
        send_telegram(msg)

    buffers.pop(key, None)

# ---------------- WEBHOOK ----------------
@app.route("/", methods=["POST"])
def webhook():
    try:
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

                wallet = tx.get("signer") or tx.get("owner")
                token = tx.get("tokenMint")
                symbol = tx.get("tokenSymbol")

                raw_amount = tx.get("nativeAmount") or tx.get("amount")
                if raw_amount is None:
                    continue

                try:
                    sol_amount = float(raw_amount)
                except:
                    continue

                if sol_amount <= 0:
                    continue

                # ❌ ignore SOL
                if token == SOL_MINT or symbol == "SOL":
                    continue

                # ❌ ignore stables
                if symbol in STABLECOINS:
                    continue

                if not wallet or not token:
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

    except Exception as e:
        print("Webhook fatal error:", e)
        return jsonify({"ok": True})


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
