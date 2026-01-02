from flask import Flask, request
import os
import time
import requests
from collections import defaultdict

app = Flask(__name__)

# ========================
# ENV
# ========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 4
AGG_WINDOW = 6 * 60 * 60        # 6 год
DEBOUNCE = 180                  # 3 хв

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_KEYWORDS = ["USD", "USDT", "USDC", "DAI", "BUSD"]

# ========================
# STATE
# ========================
alerts = {}  # token -> data

# ========================
# HELPERS
# ========================
def is_stable(token: str) -> bool:
    token_upper = token.upper()
    return any(k in token_upper for k in STABLE_KEYWORDS)

def short(addr: str) -> str:
    return f"{addr[:6]}...{addr[-4:]}"

def send(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

def axiom_link(token: str) -> str:
    return f"https://axiom.trade/token/{token}"

# ========================
# ROUTES
# ========================
@app.route("/", methods=["GET"])
def home():
    send("✅ <b>Bot is alive</b>\nRender + Telegram працюють")
    return "OK"

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time.time()

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        if tx.get("type") != "SWAP":
            continue

        for tr in tx.get("tokenTransfers", []):
            token = tr.get("mint")
            buyer = tr.get("toUserAccount")
            amount = tr.get("tokenAmount")

            if not token or not buyer or not amount:
                continue

            # filters
            if token == SOL_MINT:
                continue
            if is_stable(token):
                continue
            if amount < MIN_SOL:
                continue

            amount = round(float(amount), 2)

            alert = alerts.get(token)

            # new token
            if not alert or now - alert["start"] > AGG_WINDOW:
                alerts[token] = {
                    "start": now,
                    "last_sent": 0,
                    "wallets": {}
                }
                alert = alerts[token]

            # same wallet again → ignore
            if buyer in alert["wallets"]:
                continue

            # add wallet
            alert["wallets"][buyer] = amount

            # debounce
            if now - alert["last_sent"] < DEBOUNCE:
                continue

            # send alert
            total = round(sum(alert["wallets"].values()), 2)

            lines = []
            for i, (w, amt) in enumerate(alert["wallets"].items(), 1):
                lines.append(f"{i}. {short(w)} → {amt} SOL")

            msg = (
                "🔥 <b>MULTI BUY ALERT</b>\n\n"
                f"🪙 <b>Token:</b>\n<code>{token}</code>\n\n"
                f"👥 <b>Wallets:</b> {len(alert['wallets'])}\n"
                f"💰 <b>Total SOL:</b> {total}\n\n"
                + "\n".join(lines) +
                f"\n\n🔗 <a href='{axiom_link(token)}'>Open in Axiom</a>"
            )

            send(msg)
            alert["last_sent"] = now

    return "ok"

# ========================
# RUN
# ========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
