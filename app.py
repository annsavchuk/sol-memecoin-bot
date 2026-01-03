import os
import time
from flask import Flask, request, jsonify
import requests
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

AXIOM_URL = "https://axiom.trade/token/"
LAMPORTS_PER_SOL = Decimal("1000000000")

MIN_SOL = Decimal("4")
AGG_WINDOW = 6 * 60 * 60          # 6 hours
DEBOUNCE_WINDOW = 180             # 3 minutes

IGNORED_TOKENS = {
    "So11111111111111111111111111111111111111112"
}

STABLE_KEYWORDS = ["usd", "usdt", "usdc"]

# token -> state
state = {}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    })

def round_sol(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time.time()

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        token_out = tx.get("tokenTransfers", [])
        native = tx.get("nativeTransfers", [])

        if not token_out or not native:
            continue

        token_mint = token_out[-1]["mint"]

        # ❌ ignore SOL + stables
        if token_mint in IGNORED_TOKENS:
            continue
        if any(k in token_mint.lower() for k in STABLE_KEYWORDS):
            continue

        lamports = sum(int(n["amount"]) for n in native if n["amount"])
        sol = Decimal(lamports) / LAMPORTS_PER_SOL

        if sol < MIN_SOL:
            continue

        buyer = tx["feePayer"]

        token_state = state.setdefault(token_mint, {
            "start": now,
            "last_alert": 0,
            "wallets": {}
        })

        # ⏱ reset after 6h
        if now - token_state["start"] > AGG_WINDOW:
            state[token_mint] = {
                "start": now,
                "last_alert": 0,
                "wallets": {}
            }
            token_state = state[token_mint]

        # ❌ same wallet again → ignore
        if buyer in token_state["wallets"]:
            continue

        token_state["wallets"][buyer] = sol

        # ⏸ debounce
        if now - token_state["last_alert"] < DEBOUNCE_WINDOW:
            continue

        token_state["last_alert"] = now

        wallets = token_state["wallets"]
        total_sol = round_sol(sum(wallets.values()))

        lines = []
        for i, (w, amt) in enumerate(wallets.items(), 1):
            lines.append(
                f"{i}. {w[:6]}…{w[-4:]} → {round_sol(amt)} SOL"
            )

        message = (
            "🔥 MULTI BUY ALERT\n\n"
            f"🪙 Token:\n{token_mint}\n\n"
            f"👥 Wallets: {len(wallets)}\n"
            f"💰 Total SOL: {total_sol}\n\n"
            + "\n".join(lines)
            + f"\n\n🔗 Open in Axiom:\n{AXIOM_URL}{token_mint}"
        )

        send_telegram(message)

    return jsonify({"ok": True})
