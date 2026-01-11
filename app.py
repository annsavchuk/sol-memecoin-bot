import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= ENV =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================= CONSTANTS =================
SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDC", "USDT"}

# ================= TELEGRAM =================
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

# ================= TEST ENDPOINT =================
@app.route("/test", methods=["GET"])
def test():
    send_telegram("✅ TEST: Telegram працює")
    return "ok", 200

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("RAW PAYLOAD:", data)

        if not data:
            return jsonify({"ok": True})

        # payload приходить як список
        if isinstance(data, list):
            txs = data
        else:
            return jsonify({"ok": True})

        for tx in txs:
            try:
                tx_type = tx.get("type")
                if tx_type != "SWAP":
                    continue

                token_transfers = tx.get("tokenTransfers", [])
                native_transfers = tx.get("nativeTransfers", [])

                if not token_transfers or not native_transfers:
                    continue

                # беремо перший трансфер токена
                t = token_transfers[0]
                mint = t.get("mint")
                token_amount = t.get("tokenAmount")
                wallet = t.get("toUserAccount")

                # беремо SOL трансфер
                n = native_transfers[0]
                sol_lamports = n.get("amount")
                from_wallet = n.get("fromUserAccount")

                if not mint or not wallet or not sol_lamports:
                    continue

                # SOL -> в SOL
                sol_spent = sol_lamports / 1_000_000_000

                if sol_spent <= 0:
                    continue

                # ❌ ігноруємо SOL
                if mint == SOL_MINT:
                    continue

                # -------- ALERT --------
                msg = (
                    "🟢 BUY DETECTED\n\n"
                    f"👛 Wallet:\n{wallet}\n\n"
                    f"🪙 Token:\n{mint}\n\n"
                    f"💰 Spent:\n{sol_spent:.2f} SOL\n\n"
                    f"🔗 Axiom:\nhttps://axiom.trade/token/{mint}"
                )

                send_telegram(msg)

            except Exception as e:
                print("TX parse error:", e)

        return jsonify({"ok": True})

    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"ok": True})


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
