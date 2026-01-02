from flask import Flask, request
import os
import requests
import time
import json
from collections import defaultdict

app = Flask(__name__)

# =========================
# ENV
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =========================
# CONFIG
# =========================
WINDOW_SECONDS = 6 * 60 * 60      # 6 год
DEBOUNCE_SECONDS = 150            # 2.5 хв
SOL_MINT = "So11111111111111111111111111111111111111112"

STABLECOINS = {
    "USDt",
    "USDC",
    "USDT",
    "USDc",
    "USDtGY1N7NEEHLmELoaybftRBUSerhqYiQzvEmuB"
}

# =========================
# STATE (in-memory)
# =========================
aggregates = {}
last_sent = {}

# =========================
# TELEGRAM
# =========================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

# =========================
# FORMAT
# =========================
def short(addr):
    return f"{addr[:6]}...{addr[-4:]}"

def axiom_link(token):
    return f"https://axiom.trade/token/{token}"

# =========================
# HOME
# =========================
@app.route("/", methods=["GET"])
def home():
    send_message("✅ <b>Bot is alive</b>\nRender + Telegram працюють")
    return "OK"

# =========================
# WEBHOOK
# =========================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time.time()

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        tx_type = tx.get("type")
        transfers = tx.get("tokenTransfers", [])

        for t in transfers:
            mint = t.get("mint")
            amount = t.get("tokenAmount")
            buyer = t.get("toUserAccount")

            if not mint or not amount or not buyer:
                continue

            # ❌ SOL
            if mint == SOL_MINT:
                continue

            # ❌ Stablecoins
            if mint in STABLECOINS:
                continue

            # SOL округлення
            sol = round(float(amount), 2)
            if sol <= 0:
                continue

            # =========================
            # AGGREGATION
            # =========================
            agg = aggregates.get(mint)

            if not agg or now - agg["start"] > WINDOW_SECONDS:
                agg = {
                    "start": now,
                    "wallets": {},
                    "total": 0
                }
                aggregates[mint] = agg

            is_new_wallet = buyer not in agg["wallets"]

            agg["wallets"][buyer] = agg["wallets"].get(buyer, 0) + sol
            agg["total"] += sol

            # ❗ алерт тільки при новому гаманці
            if not is_new_wallet:
                continue

            # debounce
            if now - last_sent.get(mint, 0) < DEBOUNCE_SECONDS:
                continue

            last_sent[mint] = now

            # =========================
            # MESSAGE
            # =========================
            lines = []
            for i, (w, s) in enumerate(agg["wallets"].items(), 1):
                lines.append(f"{i}. {short(w)} → {round(s,2)} SOL")

            msg = (
                "🔥 <b>MULTI BUY ALERT</b>\n\n"
                f"🌕 <b>Token:</b>\n<code>{mint}</code>\n\n"
                f"👥 <b>Wallets:</b> {len(agg['wallets'])}\n"
                f"💰 <b>Total SOL:</b> {round(agg['total'],2)}\n\n"
                + "\n".join(lines)
                + f"\n\n🔗 <a href='{axiom_link(mint)}'>Open in Axiom</a>"
            )

            send_message(msg)

    return "ok"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
