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
MIN_TX_SOL = 0.5        # мінімальна покупка
LEVEL_1 = 9            # жовтий алерт
LEVEL_2 = 20           # червоний алерт
BUFFER_SECONDS = 90    # буфер у секундах

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDC", "USDT"}

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
        f"🧾 Buys count: {data['count']}\n\n"
        f"🔗 Axiom:\nhttps://axiom.trade/token/{token}"
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

    if not data:
        return jsonify({"ok": True})

    # -------- normalize --------
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events") or data.get("data") or []
    else:
        return jsonify({"ok": True})

    if not events:
        return jsonify({"ok": True})

    for tx in events:
        try:
            wallet = tx.get("feePayer")
            token_transfers = tx.get("tokenTransfers", [])

            if not wallet or not token_transfers:
                continue

            # ================== SOL CALC (CORRECT) ==================
            sol_spent = 0
            for acc in tx.get("accountData", []):
                if acc.get("account") == wallet:
                    change = acc.get("nativeBalanceChange", 0)

                    # якщо баланс зменшився — це витрати
                    if change < 0:
                        sol_spent = abs(change)
                        break

            sol_amount = sol_spent / 1e9

            # -------- FILTER: min buy --------
            if sol_amount < MIN_TX_SOL:
                continue

            for t in token_transfers:
                mint = t.get("mint")

                # -------- FILTERS --------
                if not mint or mint == SOL_MINT:
                    continue

                symbol = t.get("symbol")
                if symbol in STABLECOINS:
                    continue

                # -------- BUFFER --------
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
