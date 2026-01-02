from flask import Flask, request
import os
import requests
import time
from collections import defaultdict

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

AGG_WINDOW = 180          # 3 хв
MAX_LIFETIME = 6 * 3600   # 6 год

# token_mint -> state
alerts = {}

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    })

@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time.time()

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        transfers = tx.get("tokenTransfers", [])
        sol_change = abs(tx.get("nativeBalanceChange", 0)) / 1e9

        if sol_change < 4:
            continue

        for t in transfers:
            mint = t.get("mint")
            wallet = t.get("toUserAccount")

            if not mint or not wallet:
                continue

            # init state if needed
            if mint not in alerts or now - alerts[mint]["start"] > MAX_LIFETIME:
                alerts[mint] = {
                    "start": now,
                    "last_update": now,
                    "wallets": defaultdict(lambda: {"sol": 0, "tx": 0})
                }

            state = alerts[mint]

            state["wallets"][wallet]["sol"] += sol_change
            state["wallets"][wallet]["tx"] += 1
            state["last_update"] = now

            # check if we should send/update alert
            if now - state["start"] >= AGG_WINDOW and len(state["wallets"]) >= 2:
                total_sol = sum(w["sol"] for w in state["wallets"].values())

                lines = []
                for w, info in state["wallets"].items():
                    lines.append(
                        f"👤 <code>{w[:4]}…{w[-4:]}</code> → "
                        f"<b>{info['sol']:.2f} SOL</b> ({info['tx']} buys)"
                    )

                message = (
                    "🔥 <b>SMART MULTI-BUY ALERT</b>\n\n"
                    f"🪙 <b>Token:</b> <code>{mint}</code>\n"
                    f"👥 <b>Wallets:</b> {len(state['wallets'])}\n"
                    f"💰 <b>Total:</b> {total_sol:.2f} SOL\n\n"
                    + "\n".join(lines)
                    + f"\n\n🔗 <a href='https://axiom.trade/token/{mint}'>Open in Axiom</a>"
                )

                send_message(message)
                state["start"] = now  # reset aggregation window

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
