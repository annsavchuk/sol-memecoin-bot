import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    print("❌ TELEGRAM_TOKEN or CHAT_ID not set")

# ================== SETTINGS ==================
MIN_TX_SOL = 9          # мінімальний алерт
LEVEL_1 = 9            # 🟡 BUY
LEVEL_2 = 20           # 🔴 BIG BUY
BUFFER_SECONDS = 90

SOL_MINT = "So11111111111111111111111111111111111111112"

# фільтр стаблів / wrapped
STABLE_KEYWORDS = ["usd", "usdt", "usdc", "sol", "wsol", "eth", "weth", "btc", "wbtc"]

buffers = {}

# ================== TELEGRAM ==================
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# ================== ALERT FLUSH ==================
def flush_alert(key):
    time.sleep(BUFFER_SECONDS)

    data = buffers.pop(key, None)
    if not data:
        return

    total = data["total"]
    wallet = data["wallet"]
    token = data["token"]

    if total >= LEVEL_2:
        level = "🔴 BIG BUY"
    elif total >= LEVEL_1:
        level = "🟡 BUY"
    else:
        return

    text = (
        f"{level}\n\n"
        f"👛 Wallet:\n{wallet}\n\n"
        f"🪙 Token:\n{token}\n\n"
        f"💰 Total buy: {total:.2f} SOL\n"
        f"🧾 Buys count: {data['count']}"
    )

    send_telegram(text)

# ================== TEST ==================
@app.route("/test", methods=["GET"])
def test():
    send_telegram("✅ TEST: Telegram працює")
    return "ok", 200

# ================== WEBHOOK ==================
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    print("RAW PAYLOAD:", data)

    # Helius завжди шле список
    if not isinstance(data, list):
        return jsonify({"ok": True})

    for tx in data:
        try:
            wallet = tx.get("feePayer")
            token_transfers = tx.get("tokenTransfers", [])

            if not wallet or not token_transfers:
                continue

            # ---------- SOL SPENT ----------
            sol_spent = 0
            for acc in tx.get("accountData", []):
                if acc.get("account") == wallet:
                    change = acc.get("nativeBalanceChange", 0)
                    if change < 0:
                        sol_spent = abs(change)
                        break

            sol_amount = sol_spent / 1e9

            # ---------- FILTER ----------
            if sol_amount < MIN_TX_SOL:
                continue

            for t in token_transfers:
                mint = t.get("mint", "").lower()

                # ❌ не алертимо SOL
                if mint == SOL_MINT.lower():
                    continue

                # ❌ фільтр stable / wrapped
                if any(word in mint for word in STABLE_KEYWORDS):
                    continue

                key = f"{wallet}|{mint}"

                if key not in buffers:
                    buffers[key] = {
                        "wallet": wallet,
                        "token": mint,
                        "total": sol_amount,
                        "count": 1
                    }
                    threading.Thread(
                        target=flush_alert,
                        args=(key,),
                        daemon=True
                    ).start()
                else:
                    buffers[key]["total"] += sol_amount
                    buffers[key]["count"] += 1

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
