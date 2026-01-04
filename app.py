import os
import time
from decimal import Decimal, ROUND_DOWN
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ===== ENV =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

# ===== CONFIG =====
MIN_SOL = Decimal("4.0")
AGG_WINDOW = 6 * 60 * 60
DEBOUNCE = 120
LAMPORTS = Decimal("1000000000")
FEE_CUTOFF = Decimal("0.3")

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_KEYWORDS = ("usd", "usdt", "usdc", "uxd", "dai")

STATE = {}

# ===== HELPERS =====
def now():
    return int(time.time())

def q(d):
    return d.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

def short(a):
    return f"{a[:6]}…{a[-4:]}" if a and len(a) > 10 else a

def is_stable(m):
    return any(k in m.lower() for k in STABLE_KEYWORDS)

def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

# ===== CORE PARSING =====
def find_buyer(tx):
    return (
        tx.get("feePayer")
        or tx.get("userAccount")
        or next((t.get("toUserAccount") for t in tx.get("tokenTransfers", []) if t.get("toUserAccount")), None)
    )

def find_token(tx, buyer):
    for t in tx.get("tokenTransfers", []):
        if t.get("toUserAccount") == buyer:
            mint = t.get("mint")
            if mint and mint != SOL_MINT and not is_stable(mint):
                return mint
    return None

def extract_sol(tx, buyer, token):
    # --- Level 1: structured swap ---
    for key in ("swap", "swaps", "parsedSwaps", "swapInfo"):
        swaps = tx.get(key)
        if not swaps:
            continue
        if isinstance(swaps, dict):
            swaps = [swaps]
        for s in swaps:
            out = s.get("outputMint") or s.get("outMint")
            if out != token:
                continue
            lamports = s.get("inAmount") or s.get("inputAmount")
            if lamports:
                sol = q(Decimal(str(lamports)) / LAMPORTS)
                return sol, False

    # --- Level 2: fallback (SOL outflow) ---
    lamports_out = Decimal("0")
    for n in tx.get("nativeTransfers", []):
        if n.get("fromUserAccount") == buyer:
            lamports_out += abs(Decimal(str(n.get("amount", 0))))

    sol = q(lamports_out / LAMPORTS)
    if sol > MIN_SOL + FEE_CUTOFF:
        return q(sol - FEE_CUTOFF), True

    return Decimal("0"), False

# ===== WEBHOOK =====
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        data = [data]

    for tx in data:
        if tx.get("type") and tx.get("type") != "SWAP":
            continue

        buyer = find_buyer(tx)
        if not buyer:
            continue

        token = find_token(tx, buyer)
        if not token:
            continue

        sol, approx = extract_sol(tx, buyer, token)
        if sol < MIN_SOL:
            continue

        ts = now()
        bucket = STATE.get(token)

        if not bucket or ts - bucket["start"] > AGG_WINDOW:
            bucket = {"start": ts, "wallets": {}, "last_alert": 0}
            STATE[token] = bucket

        if buyer in bucket["wallets"]:
            w = bucket["wallets"][buyer]
            w["total"] = q(w["total"] + sol)
            w["last"] = sol
            continue

        bucket["wallets"][buyer] = {"total": sol, "last": sol}

        if ts - bucket["last_alert"] < DEBOUNCE:
            continue

        bucket["last_alert"] = ts
        total = q(sum(w["total"] for w in bucket["wallets"].values()))

        msg = [
            "🔥 <b>MULTI BUY ALERT</b>\n",
            f"🪙 <code>{token}</code>",
            f"👥 Wallets: {len(bucket['wallets'])}",
            f"💰 Total SOL: {total}\n"
        ]

        i = 1
        for w, v in bucket["wallets"].items():
            tag = "~" if approx else ""
            msg.append(f"{i}. <code>{short(w)}</code> → last: {tag}{v['last']} SOL (total: {v['total']} SOL)")
            i += 1

        msg.append(f"\n🔗 <a href='https://axiom.trade/token/{token}'>Open in Axiom</a>")
        send("\n".join(msg))

    return jsonify(ok=True)

@app.route("/", methods=["GET"])
def home():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
