from flask import Flask, request
import os
import requests
import time
import threading

app = Flask(__name__)

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_SOL = 0.1
AGGREGATION_WINDOW = 180        # 3 хв
TRACKING_WINDOW = 6 * 60 * 60   # 6 год

SOL_MINT = "So11111111111111111111111111111111111111112"

# ================== MEMORY ==================
# token_mint -> {
#   first_seen, last_update,
#   wallets: { wallet: sol_amount }
# }
active_tokens = {}

lock = threading.Lock()

# ================== TELEGRAM ==================
def send_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================== AXIOM LINK ==================
def axiom_link(token):
    return f"https://axiom.trade/token/{token}"

# ================== FORMAT ALERT ==================
def format_alert(token, data):
    wallets = data["wallets"]
    total_sol = round(sum(wallets.values()), 2)

    lines = [
        "🔥 <b>MULTI BUY ALERT</b>",
        "",
        f"🪙 <b>Token:</b>",
        f"<code>{token}</code>",
        "",
        f"👥 <b>Wallets:</b> {len(wallets)}",
        f"💰 <b>Total SOL:</b> {total_sol}",
        ""
    ]

    for i, (wallet, amount) in enumerate(wallets.items(), start=1):
        lines.append(
            f"{i}. <code>{wallet[:6]}...{wallet[-4:]}</code> → {round(amount, 2)} SOL"
        )

    lines.append("")
    lines.append(f"🔗 <a href='{axiom_link(token)}'>Open in Axiom</a>")

    return "\n".join(lines)

# ================== WEBHOOK ==================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        return "ok"

    now = time.time()

    with lock:
        for tx in data:
            if tx.get("type") not in ["SWAP", "TRANSFER"]:
                continue

            for tr in tx.get("tokenTransfers", []):
                mint = tr.get("mint")
                amount = tr.get("tokenAmount")
                wallet = tr.get("toUserAccount")

                if not mint or not wallet or not amount:
                    continue

                # ❌ IGNORE SOL
                if mint == SOL_MINT:
                    continue

                sol_amount = round(float(amount), 2)

                if sol_amount < MIN_SOL:
                    continue

                token_data = active_tokens.get(mint)

                # 🆕 NEW TOKEN
                if not token_data:
                    active_tokens[mint] = {
                        "first_seen": now,
                        "last_update": now,
                        "wallets": {wallet: sol_amount}
                    }
                    send_message(format_alert(mint, active_tokens[mint]))
                    continue

                # ⏰ EXPIRED → NEW ALERT
                if now - token_data["first_seen"] > TRACKING_WINDOW:
                    active_tokens[mint] = {
                        "first_seen": now,
                        "last_update": now,
                        "wallets": {wallet: sol_amount}
                    }
                    send_message(format_alert(mint, active_tokens[mint]))
                    continue

                # ➕ UPDATE EXISTING
                wallets = token_data["wallets"]

                if wallet in wallets:
                    # same wallet → add amount
                    wallets[wallet] = round(wallets[wallet] + sol_amount, 2)
                else:
                    wallets[wallet] = sol_amount

                token_data["last_update"] = now

                send_message(format_alert(mint, token_data))

    return "ok"

# ================== HEALTH ==================
@app.route("/", methods=["GET"])
def home():
    send_message("✅ <b>Bot is alive</b>\nAggregation logic active")
    return "Bot is running"

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
