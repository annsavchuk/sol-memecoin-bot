from flask import Flask, request
import os
import requests
import json
from collections import defaultdict
from time import time

app = Flask(__name__)

# ENV
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SOL_MINT = "So11111111111111111111111111111111"
MIN_SOL = 4

# cache for grouping buys
buy_cache = defaultdict(list)
CACHE_TTL = 120  # seconds


def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM config")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })


@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time()

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        transfers = tx.get("tokenTransfers", [])
        if not transfers:
            continue

        sol_spent = 0
        token_mint = None
        buyer = None

        for t in transfers:
            mint = t.get("mint")
            amount = float(t.get("tokenAmount", 0))
            from_user = t.get("fromUserAccount")
            to_user = t.get("toUserAccount")

            if mint == SOL_MINT:
                sol_spent += amount
                buyer = from_user
            else:
                token_mint = mint

        if not token_mint or sol_spent <= 0:
            continue

        # save to cache
        buy_cache[token_mint].append({
            "wallet": buyer,
            "sol": sol_spent,
            "time": now
        })

    # cleanup + alerts
    for mint, buys in list(buy_cache.items()):
        buys = [b for b in buys if now - b["time"] <= CACHE_TTL]
        buy_cache[mint] = buys

        total_sol = sum(b["sol"] for b in buys)

        if total_sol >= MIN_SOL:
            wallets = {}
            for b in buys:
                wallets[b["wallet"]] = wallets.get(b["wallet"], 0) + b["sol"]

            lines = "\n".join(
                f"• <code>{w[:6]}...{w[-4:]}</code> | {round(sol,2)} SOL"
                for w, sol in wallets.items()
            )

            message = (
                "🟢 <b>BUY ALERT</b>\n\n"
                f"🪙 <b>Token:</b>\n<code>{mint}</code>\n\n"
                f"💰 <b>Total buy:</b> {round(total_sol,2)} SOL\n"
                f"👛 <b>Wallets:</b>\n{lines}\n\n"
                f"🔥 <b>Wallets count:</b> {len(wallets)}"
            )

            send_message(message)
            del buy_cache[mint]

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
