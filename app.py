import os
import time
from collections import defaultdict
from flask import Flask, request, jsonify
import requests

# ========= CONFIG =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID")

# thresholds
MIN_ALERT_SOL = 4
BIG_ALERT_SOL = 20

# aggregation window (seconds)
AGG_WINDOW = 90

# ==========================

app = Flask(__name__)

# storage for aggregation
# key = (wallet, token)
# value = { total, count, first_ts }
pending = {}

# ---------- helpers ----------

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def flush_if_needed(key):
    data = pending.get(key)
    if not data:
        return

    now = time.time()
    if now - data["first_ts"] < AGG_WINDOW:
        return

    total = data["total"]
    count = data["count"]
    wallet, token = key

    if total >= MIN_ALERT_SOL:
        level = "🔴 BIG BUY" if total >= BIG_ALERT_SOL else "🟢 BUY DETECTED"

        msg = (
            f"{level}\n\n"
            f"👛 Wallet:\n{wallet}\n\n"
            f"🪙 Token:\n{token}\n\n"
            f"💰 Total amount: {total:.2f} SOL\n"
            f"🧾 Buys count: {count}\n\n"
            f"🔗 Open in Axiom\n"
            f"https://axiom.trade/token/{token}"
        )
        send_telegram(msg)

    del pending[key]


def add_to_aggregation(wallet, token, amount):
    key = (wallet, token)
    now = time.time()

    if key not in pending:
        pending[key] = {
            "total": amount,
            "count": 1,
            "first_ts": now
        }
    else:
        pending[key]["total"] += amount
        pending[key]["count"] += 1

    flush_if_needed(key)


# ---------- webhook ----------

@app.route("/", methods=["POST"])
def helius_webhook():
    payload = request.json
    print("Incoming payload:", payload)

    if not isinstance(payload, list):
        return jsonify({"ok": True})

    for tx in payload:
        # we only care about SWAP / TOKEN TRANSFER style buys
        events = tx.get("events", {})
        swap = events.get("swap")

        if not swap:
            continue

        # we want SOL -> token (buy)
        native_in = swap.get("nativeInput")
        token_out = swap.get("tokenOutputs")

        if not native_in or not token_out:
            continue

        sol_amount = native_in.get("amount", 0) / 1e9
        if sol_amount <= 0:
            continue

        buyer = swap.get("user")
        token_mint = token_out[0].get("mint") if token_out else None

        if not buyer or not token_mint:
            continue

        print("BUY:", buyer, token_mint, sol_amount)

        add_to_aggregation(buyer, token_mint, sol_amount)

    return jsonify({"ok": True})


# ---------- test endpoint ----------

@app.route("/test", methods=["GET"])
def test_alert():
    wallet = "TEST_WALLET_123"
    token = "TEST_TOKEN_ABC"
    total = 12.5
    count = 1

    msg = (
        f"🧪 TEST ALERT\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total amount: {total} SOL\n"
        f"🧾 Buys count: {count}\n\n"
        f"https://axiom.trade/token/{token}"
    )
    send_telegram(msg)
    return "Test alert sent"


# ---------- run ----------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
