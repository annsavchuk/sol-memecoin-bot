from flask import Flask, request
import os
import requests
import time
import json

app = Flask(__name__)

# === ENV ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === CONFIG ===
MIN_SOL = 4
AGG_WINDOW = 180          # 3 minutes
ALERT_LIFETIME = 6 * 3600 # 6 hours

# === IN-MEMORY STORAGE ===
token_alerts = {}  # mint -> alert data


def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    requests.post(url, json=payload, timeout=10)


def build_alert_message(mint, data):
    total_sol = round(sum(w["sol"] for w in data["wallets"].values()), 2)
    wallets_count = len(data["wallets"])

    lines = []
    for i, (wallet, info) in enumerate(data["wallets"].items(), start=1):
        lines.append(f"{i}. <code>{wallet[:6]}...{wallet[-4:]}</code> → {info['sol']} SOL")

    axiom_link = f"https://axiom.trade/token/{mint}"

    message = (
        f"🔥 <b>MULTI BUY ALERT</b>\n\n"
        f"🪙 <b>Token:</b> <code>{mint}</code>\n"
        f"👥 <b>Wallets:</b> {wallets_count}\n"
        f"💰 <b>Total SOL:</b> {total_sol}\n\n"
        + "\n".join(lines) +
        f"\n\n🔗 <a href='{axiom_link}'>Open in Axiom</a>"
    )
    return message


@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    now = time.time()

    if not isinstance(data, list):
        return "ok"

    for tx in data:
        transfers = tx.get("tokenTransfers", [])
        native = tx.get("nativeTransfers", [])

        if not transfers or not native:
            continue

        sol_spent = sum(
            t.get("amount", 0) for t in native if t.get("fromUserAccount")
        ) / 1e9

        if sol_spent < MIN_SOL:
            continue

        for t in transfers:
            mint = t.get("mint")
            wallet = t.get("toUserAccount")

            if not mint or not wallet:
                continue

            alert = token_alerts.get(mint)

            # === NEW ALERT OR EXPIRED ===
            if not alert or now - alert["created_at"] > ALERT_LIFETIME:
                token_alerts[mint] = {
                    "created_at": now,
                    "last_update": now,
                    "wallets": {
                        wallet: {"sol": round(sol_spent, 2)}
                    }
                }
                send_message(build_alert_message(mint, token_alerts[mint]))
                continue

            # === AGGREGATION ===
            alert["last_update"] = now

            if wallet in alert["wallets"]:
                alert["wallets"][wallet]["sol"] += round(sol_spent, 2)
            else:
                alert["wallets"][wallet] = {"sol": round(sol_spent, 2)}

            send_message(build_alert_message(mint, alert))

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
