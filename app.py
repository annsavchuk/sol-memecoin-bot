import os
import time
from collections import defaultdict
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MIN_SOL = 4
AGG_WINDOW = 6 * 60 * 60      # 6 hours
DEBOUNCE = 120                # 2 minutes

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_MINT_PREFIXES = ("USD", "USDT", "USDC", "UXD")

state = {}

def now():
    return int(time.time())

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify(ok=True)

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        timestamp = tx.get("timestamp", now())
        if now() - timestamp > AGG_WINDOW:
            continue

        transfers = tx.get("nativeTransfers", [])
        token_transfers = tx.get("tokenTransfers", [])

        # --- determine token mint ---
        token_mint = None
        for t in token_transfers:
            mint = t.get("mint", "")
            if mint and mint != SOL_MINT and not mint.startswith(STABLE_MINT_PREFIXES):
                token_mint = mint
                break

        if not token_mint:
            continue

        # --- SOL spent ---
        sol_spent = 0.0
        buyer = None

        for t in transfers:
            if t.get("fromUserAccount") and t.get("toUserAccount"):
                buyer = t["fromUserAccount"]
                sol_spent += t.get("amount", 0) / 1_000_000_000

        sol_spent = round(sol_spent, 2)
        if sol_spent < MIN_SOL or not buyer:
            continue

        token_state = state.setdefault(token_mint, {
            "wallets": {},
            "first_seen": timestamp,
            "last_alert": 0
        })

        # --- aggregation window ---
        if timestamp - token_state["first_seen"] > AGG_WINDOW:
            state[token_mint] = {
                "wallets": {},
                "first_seen": timestamp,
                "last_alert": 0
            }
            token_state = state[token_mint]

        is_new_wallet = buyer not in token_state["wallets"]
        token_state["wallets"][buyer] = token_state["wallets"].get(buyer, 0) + sol_spent

        if not is_new_wallet:
            continue

        if now() - token_state["last_alert"] < DEBOUNCE:
            continue

        token_state["last_alert"] = now()

        total_sol = round(sum(token_state["wallets"].values()), 2)

        lines = [
            "🔥 MULTI BUY ALERT",
            "",
            f"🪙 Token:",
            token_mint,
            "",
            f"👥 Wallets: {len(token_state['wallets'])}",
            f"💰 Total SOL: {total_sol}",
            ""
        ]

        for i, (w, amt) in enumerate(token_state["wallets"].items(), 1):
            short = f"{w[:6]}...{w[-4:]}"
            lines.append(f"{i}. {short} → {round(amt,2)} SOL")

        lines.append("")
        lines.append(f"🔗 https://axiom.trade/token/{token_mint}")

        send_telegram("\n".join(lines))

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
