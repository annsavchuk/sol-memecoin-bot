import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== ENV ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID env variable")

# ========== CONFIG ==========
MIN_SOL = 9.0
STRONG_SOL = 20.0
WINDOW_SECONDS = 90

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDT", "USDt", "USDC", "USDCet"}

# key = wallet|token
buffers = {}

# ========== HELPERS ==========
def send_telegram(text):
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


def build_and_send_alert(data):
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


# ========== WEBHOOK ==========
@app.route("/", methods=["POST"])
def webhook():
    now = time.time()
    data = request.json

    if not data:
        return jsonify({"ok": True})

    for tx in data.get("events", []):
        try:
            wallet = tx.get("signer")
            token = tx.get("tokenMint")
            symbol = tx.get("tokenSymbol", "")
            sol_amount = float(tx.get("nativeAmount", 0))

            # -------- filters --------
            if not wallet or not token:
                continue
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
                    "count": 1,
                    "first_seen": now
                }
            else:
                buf = buffers[key]
                buf["total"] += sol_amount
                buf["count"] += 1

                # ⏱ check window
                if
