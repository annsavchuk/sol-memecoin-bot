import time
from flask import Flask, request, jsonify
import requests
from collections import defaultdict

app = Flask(__name__)

# ================== CONFIG ==================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_MINTS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
}

MIN_SOL = 4
AGG_WINDOW = 6 * 60 * 60        # 6 hours
DEBOUNCE = 180                 # 3 minutes

# ================== STATE ==================
aggregates = {}  # token -> data

# ================== HELPERS ==================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    requests.post(url, json=payload)

def now():
    return int(time.time())

def short(addr):
    return addr[:6] + "..." + addr[-4:]

# ================== CORE ==================
@app.route("/", methods=["POST"])
def webhook():
    events = request.json
    if not isinstance(events, list):
        return jsonify(ok=True)

    for tx in events:
        if tx.get("type") != "SWAP":
            continue

        wallet = tx.get("feePayer")
        token_mint = None
        sol_spent = 0

        # --- get SOL spent ---
        for nt in tx.get("nativeTransfers", []):
            if nt["fromUserAccount"] == wallet:
                sol_spent += nt["amount"] / 1e9

        if sol_spent < MIN_SOL:
            continue

        # --- get bought token ---
        for t in tx.get("tokenTransfers", []):
            if t["toUserAccount"] == wallet:
                token_mint = t["mint"]

        if not token_mint:
            continue

        if token_mint == SOL_MINT or token_mint in STABLE_MINTS:
            continue

        sol_spent = round(sol_spent, 2)

        entry = aggregates.get(token_mint)
        ts = now()

        if not entry or ts - entry["start"] > AGG_WINDOW:
            aggregates[token_mint] = {
                "start": ts,
                "last_sent": 0,
                "wallets": {},
            }
            entry = aggregates[token_mint]

        # ❌ same wallet — ignore
        if wallet in entry["wallets"]:
            continue

        entry["wallets"][wallet] = sol_spent

        # debounce
        if ts - entry["last_sent"] < DEBOUNCE:
            continue

        entry["last_sent"] = ts

        total = round(sum(entry["wallets"].values()), 2)

        lines = [
            "🔥 MULTI BUY ALERT",
            "",
            f"🌕 Token:",
            token_mint,
            "",
            f"👥 Wallets: {len(entry['wallets'])}",
            f"💰 Total SOL: {total}",
            "",
        ]

        for i, (w, amt) in enumerate(entry["wallets"].items(), 1):
            lines.append(f"{i}. {short(w)} → {amt} SOL")

        lines.append("")
        lines.append(f"🔗 Open in Axiom:")
        lines.append(f"https://axiom.trade/token/{token_mint}")

        send_telegram("\n".join(lines))

    return jsonify(ok=True)

# ================== RUN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
