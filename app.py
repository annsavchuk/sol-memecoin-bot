import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== ENV ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or CHAT_ID env variable")

# ========== CONFIG ==========
MIN_SOL = 9.0
STRONG_SOL = 20.0

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLECOINS = {"USDT", "USDt", "USDC", "USDCet"}


# ========== TELEGRAM ==========
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)


# ========== TEST ENDPOINT ==========
@app.route("/test", methods=["GET"])
def test():
    send_telegram("✅ TEST: Telegram працює")
    return "ok", 200


# ========== WEBHOOK ==========
@app.route("/", methods=["POST"])
def webhook():
  print("RAW PAYLOAD:", request.json)
    data = request.json

    if not data:
        return jsonify({"ok": True})

    # ---- NORMALIZE PAYLOAD ----
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events", [])
    else:
        return jsonify({"ok": True})

    if not events:
        return jsonify({"ok": True})

    for tx in events:
        try:
            wallet = tx.get("signer")
            token = tx.get("tokenMint")
            symbol = tx.get("tokenSymbol", "")

            raw_amount = tx.get("nativeAmount")
            if raw_amount is None:
                continue

            try:
                sol_amount = float(raw_amount)
            except:
                continue

            # -------- FILTERS --------
            if sol_amount <= 0:
                continue

            # ❌ не реагуємо на SOL
            if token == SOL_MINT or symbol == "SOL":
                continue

            # ❌ не реагуємо на стейбли
            if symbol in STABLECOINS:
                continue

            if not wallet or not token:
                continue

            # -------- THRESHOLDS --------
            if sol_amount < MIN_SOL:
                continue

            if sol_amount >= STRONG_SOL:
                title = "🔥🔥 STRONG BUY"
                subtitle = "⚠️ High conviction accumulation"
            else:
                title = "🟢 BUY DETECTED"
                subtitle = ""

            axiom_link = f"https://axiom.trade/token/{token}"

            message = (
                f"{title}\n\n"
                f"{subtitle}\n\n"
                f"👛 Wallet:\n{wallet}\n\n"
                f"🪙 Token:\n{token}\n\n"
                f"💰 Amount: {round(sol_amount,2)} SOL\n\n"
                f"🔗 Open in Axiom\n{axiom_link}"
            )

            send_telegram(message)

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})


# ========== HEALTH ==========
@app.route("/", methods=["GET"])
def health():
    return "OK", 200


# ========== START ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
