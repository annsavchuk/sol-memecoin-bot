from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

# ======================
# ENV VARIABLES
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 4
SOL_MINT = "So11111111111111111111111111111111111111112"

# ======================
# LOAD SMART WALLETS
# ======================
def load_wallets():
    wallets = set()
    try:
        with open("wallets.txt", "r") as f:
            for line in f:
                w = line.strip()
                if w:
                    wallets.add(w)
    except Exception as e:
        print("Wallets load error:", e)
    return wallets

SMART_WALLETS = load_wallets()

# ======================
# TELEGRAM
# ======================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Missing Telegram envs")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram:", r.text)
    except Exception as e:
        print("Telegram error:", e)

# ======================
# HOME (TEST)
# ======================
@app.route("/", methods=["GET"])
def home():
    send_message("✅ <b>Bot is alive</b>\nRender + Telegram працюють")
    return "Bot is running"

# ======================
# WEBHOOK FROM HELIUS
# ======================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    print("=== WEBHOOK RECEIVED ===")
    print(json.dumps(data, indent=2))

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
            amount = t.get("tokenAmount", 0)
            to_user = t.get("toUserAccount")
            from_user = t.get("fromUserAccount")

            # SOL витрата
            if mint == SOL_MINT and amount:
                sol_spent += float(amount)
                buyer = from_user

            # Мем токен (вхід)
            if mint != SOL_MINT and amount:
                token_mint = mint

        if not buyer or not token_mint:
            continue

        if buyer not in SMART_WALLETS:
            continue

        if sol_spent < MIN_SOL:
            continue

        axiom_link = f"https://axiom.trade/token/{token_mint}"

        message = (
            "🚨 <b>BUY ALERT</b>\n\n"
            f"💰 <b>Amount:</b> {round(sol_spent, 2)} SOL\n"
            f"👤 <b>Buyer:</b>\n<code>{buyer}</code>\n\n"
            f"🪙 <b>Token:</b>\n<code>{token_mint}</code>\n\n"
            f"🔗 <a href='{axiom_link}'>Open in Axiom</a>"
        )

        send_message(message)

    return "ok"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
