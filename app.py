import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========= ENV =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========= CONFIG =========
MIN_SOL = 4.0
AGG_WINDOW = 6 * 60 * 60      # 6 hours
DEBOUNCE = 120               # 2 minutes

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_KEYWORDS = ["usd", "usdt", "usdc", "uxd"]

# token_mint -> state
STATE = {}

# ========= HELPERS =========
def now():
    return int(time.time())

def short(addr):
    return f"{addr[:6]}…{addr[-4:]}"

def is_stable(mint: str):
    m = mint.lower()
    return any(k in m for k in STABLE_KEYWORDS)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    })

def axiom_link(token):
    return f"https://axiom.trade/token/{token}"

# ========= CORE =========
@app.route("/", methods=["POST"])
def webhook():
    payload = request.json
    if not isinstance(payload, list):
        return jsonify(ok=True)

    for tx in payload:
        if tx.get("type") != "SWAP":
            continue

        # -------- buyer --------
        buyer = tx.get("feePayer")
        if not buyer:
            buyer = tx.get("userAccount")

        # -------- find bought token (balance INCREASE) --------
        bought_token = None
        for t in tx.get("tokenTransfers", []):
            if t.get("toUserAccount") == buyer:
                mint = t.get("mint")
                if mint and mint != SOL_MINT and not is_stable(mint):
                    bought_token = mint
                    break

        if not bought_token:
            continue

        # -------- calculate SOL spent --------
        sol_spent = 0.0
        for n in tx.get("nativeTransfers", []):
            if n.get("fromUserAccount") == buyer:
                sol_spent += abs(n.get("amount", 0)) / 1_000_000_000

        sol_spent = round(sol_spent, 2)
        if sol_spent < MIN_SOL:
            continue

        ts = now()

        bucket = STATE.get(bought_token)
        if not bucket or ts - bucket["start"] > AGG_WINDOW:
            bucket = {
                "start": ts,
                "wallets": {},
                "last_alert": 0
            }
            STATE[bought_token] = bucket

        # -------- only NEW wallet triggers --------
        if buyer in bucket["wallets"]:
            continue

        bucket["wallets"][buyer] = sol_spent

        # debounce
        if ts - bucket["last_alert"] < DEBOUNCE:
            continue

        bucket["last_alert"] = ts

        total = round(sum(bucket["wallets"].values()), 2)

        lines = [
            "🔥 MULTI BUY ALERT",
            "",
            f"🪙 Token:",
            bought_token,
            "",
            f"👥 Wallets: {len(bucket['wallets'])}",
            f"💰 Total SOL: {total}",
            ""
        ]

        for i, (w, amt) in enumerate(bucket["wallets"].items(), 1):
            lines.append(f"{i}. {short(w)} → {amt} SOL")

        lines += [
            "",
            f"🔗 Open in Axiom",
            axiom_link(bought_token)
        ]

        send_telegram("\n".join(lines))

    return jsonify(ok=True)

# ========= RUN =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
