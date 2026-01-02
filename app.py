import time
import json
import threading
from collections import defaultdict
from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["TG_CHAT"]

AGG_WINDOW = 6 * 60 * 60        # 6 годин
DEBOUNCE = 180                  # 3 хв
MIN_SOL = 4.0

STABLE_MINT_KEYWORDS = ["usdt", "usdc"]
SOL_MINT = "So11111111111111111111111111111111111111112"

state = {}

def now():
    return int(time.time())

def is_stable(mint: str):
    m = mint.lower()
    return any(k in m for k in STABLE_MINT_KEYWORDS)

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True}
    )

def format_sol(x):
    return round(x, 2)

@app.route("/", methods=["POST"])
def hook():
    data = request.json
    if not data:
        return "ok"

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        buyer = tx.get("feePayer")
        swap = tx.get("swap", {})
        token_out = swap.get("tokenOutputs", [])

        if not token_out:
            continue

        token = token_out[0].get("mint")
        if not token or token == SOL_MINT or is_stable(token):
            continue

        native_input = swap.get("nativeInput", 0)
        sol = native_input / 1_000_000_000

        if sol < MIN_SOL:
            continue

        ts = now()

        bucket = state.setdefault(token, {
            "start": ts,
            "wallets": {},
            "last_sent": 0
        })

        # reset window
        if ts - bucket["start"] > AGG_WINDOW:
            bucket["start"] = ts
            bucket["wallets"] = {}
            bucket["last_sent"] = 0

        is_new_wallet = buyer not in bucket["wallets"]
        bucket["wallets"][buyer] = bucket["wallets"].get(buyer, 0) + sol

        if not is_new_wallet:
            continue

        if ts - bucket["last_sent"] < DEBOUNCE:
            continue

        bucket["last_sent"] = ts

        total = sum(bucket["wallets"].values())
        wallets = list(bucket["wallets"].items())

        lines = [
            "🔥 MULTI BUY ALERT",
            f"🪙 Token:",
            token,
            f"👥 Wallets: {len(wallets)}",
            f"💰 Total SOL: {format_sol(total)}",
            ""
        ]

        for i, (w, amt) in enumerate(wallets, 1):
            lines.append(f"{i}. {w[:6]}…{w[-4:]} → {format_sol(amt)} SOL")

        lines.append("")
        lines.append(f"🔗 https://axiom.trade/token/{token}")

        send("\n".join(lines))

    return "ok"

if __name__ == "__main__":
    app.run(port=10000)
