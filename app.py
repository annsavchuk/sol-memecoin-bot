import time
import json
from flask import Flask, request
import requests
from collections import defaultdict

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

MIN_SOL = 4
AGG_WINDOW_SEC = 6 * 60 * 60      # 6 hours
DEBOUNCE_SEC = 180               # 3 minutes

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_MINTS = {
    "USDt",
    "USDC",
    "USDT",
}

# token_mint -> data
state = {}

# ================== HELPERS ==================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False
    }
    requests.post(url, json=payload)

def short(addr):
    return f"{addr[:6]}...{addr[-4:]}"

def now():
    return int(time.time())

def axiom_link(mint):
    return f"https://axiom.trade/token/{mint}"

# ================== CORE ==================

@app.route("/", methods=["POST"])
def webhook():
    events = request.json
    if not isinstance(events, list):
        return "ok"

    for tx in events:
        if tx.get("type") != "SWAP":
            continue

        token_mint = None
        buyer = tx.get("feePayer")

        # --- detect token mint (non SOL, non stable) ---
        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint and mint not in STABLE_MINTS and mint != SOL_MINT:
                token_mint = mint
                break

        if not token_mint:
            continue

        # --- get SOL spent ---
        sol_spent = 0.0
        for n in tx.get("nativeTransfers", []):
            if n.get("fromUserAccount") == buyer:
                lamports = abs(n.get("amount", 0))
                sol_spent += lamports / 1_000_000_000

        sol_spent = round(sol_spent, 2)
        if sol_spent < MIN_SOL:
            continue

        ts = now()

        bucket = state.get(token_mint)
        if not bucket or ts - bucket["start"] > AGG_WINDOW_SEC:
            bucket = {
                "start": ts,
                "wallets": {},
                "last_alert": 0
            }
            state[token_mint] = bucket

        # --- only alert on NEW wallet ---
        if buyer in bucket["wallets"]:
            continue

        bucket["wallets"][buyer] = sol_spent

        # debounce
        if ts - bucket["last_alert"] < DEBOUNCE_SEC:
            continue

        bucket["last_alert"] = ts

        total_sol = round(sum(bucket["wallets"].values()), 2)

        lines = [
            "🔥 MULTI BUY ALERT",
            "",
            f"🪙 Token:",
            token_mint,
            "",
            f"👥 Wallets: {len(bucket['wallets'])}",
            f"💰 Total SOL: {total_sol}",
            ""
        ]

        for i, (w, amt) in enumerate(bucket["wallets"].items(), 1):
            lines.append(f"{i}. {short(w)} → {amt} SOL")

        lines.append("")
        lines.append(f"🔗 Open in Axiom")
        lines.append(axiom_link(token_mint))

        send_telegram("\n".join(lines))

    return "ok"
