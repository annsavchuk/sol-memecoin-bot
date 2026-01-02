from flask import Flask, request
import requests
import time
from collections import defaultdict

app = Flask(__name__)

# ================= CONFIG =================

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

MIN_SOL = 4.0
AGG_WINDOW = 6 * 60 * 60        # 6 hours
DEBOUNCE = 180                  # 3 minutes

SOL_MINT = "So11111111111111111111111111111111111111112"

STABLE_KEYWORDS = ["usd", "usdt", "usdc", "usdb"]

# ================= STATE =================

token_state = defaultdict(lambda: {
    "wallets": {},
    "last_update": 0,
    "last_alert": 0
})

# ================= HELPERS =================

def is_stablecoin(mint: str):
    m = mint.lower()
    return any(k in m for k in STABLE_KEYWORDS)

def lamports_to_sol(value):
    return round(value / 1_000_000_000, 2)

def short(addr):
    return addr[:5] + "..." + addr[-4:]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    })

def build_message(token, wallets):
    total = round(sum(wallets.values()), 2)
    lines = [
        "🔥 MULTI BUY ALERT",
        "",
        f"🪙 Token:",
        token,
        "",
        f"👥 Wallets: {len(wallets)}",
        f"💰 Total SOL: {total}",
        ""
    ]

    for i, (w, amt) in enumerate(wallets.items(), 1):
        lines.append(f"{i}. {short(w)} → {amt} SOL")

    lines += [
        "",
        f"🔗 Open in Axiom",
        f"https://axiom.trade/token/{token}"
    ]

    return "\n".join(lines)

# ================= WEBHOOK =================

@app.route("/", methods=["POST"])
def helius():
    events = request.json
    now = time.time()

    for tx in events:
        if tx.get("type") != "SWAP":
            continue

        native = tx.get("nativeInput", 0)
        if native == 0:
            continue

        sol_amount = lamports_to_sol(native)
        if sol_amount < MIN_SOL:
            continue

        wallet = tx.get("feePayer")
        token = None

        for t in tx.get("tokenTransfers", []):
            if t.get("mint") != SOL_MINT:
                token = t.get("mint")
                break

        if not token:
            continue

        if token == SOL_MINT or is_stablecoin(token):
            continue

        state = token_state[token]

        # reset window if expired
        if now - state["last_update"] > AGG_WINDOW:
            state["wallets"] = {}

        is_new_wallet = wallet not in state["wallets"]
        state["wallets"][wallet] = sol_amount
        state["last_update"] = now

        if not is_new_wallet:
            continue

        if now - state["last_alert"] < DEBOUNCE:
            continue

        message = build_message(token, state["wallets"])
        send_telegram(message)
        state["last_alert"] = now

    return {"ok": True}

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
