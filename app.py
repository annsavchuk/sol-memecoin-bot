import os
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_TX_SOL = 9
MULTI_LIFETIME = 21600  # 6 год

SOL_MINT = "So11111111111111111111111111111111111111112"

multi_buffer = {}


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})


def cleanup():
    while True:
        now = time.time()
        for mint in list(multi_buffer.keys()):
            if now - multi_buffer[mint]["last"] > MULTI_LIFETIME:
                del multi_buffer[mint]
        time.sleep(60)


threading.Thread(target=cleanup, daemon=True).start()


@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"ok": True})

    for tx in data:
        wallet = tx.get("feePayer")
        token_transfers = tx.get("tokenTransfers", [])
        if not wallet or not token_transfers:
            continue

        sol_spent = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet and acc.get("nativeBalanceChange", 0) < 0:
                sol_spent = abs(acc["nativeBalanceChange"])
                break

        sol_amount = sol_spent / 1e9
        if sol_amount < MIN_TX_SOL:
            continue

        for t in token_transfers:
            mint = t.get("mint")
            if not mint or mint == SOL_MINT:
                continue

            now = time.time()

            if mint not in multi_buffer:
                multi_buffer[mint] = {
                    "wallets": {wallet},
                    "total": sol_amount,
                    "last": now
                }

                send_telegram(
                    f"🟢 SINGLE BUY\n\nWallet:\n{wallet}\nMint:\n{mint}\nAmount: {sol_amount:.2f} SOL"
                )

            else:
                buf = multi_buffer[mint]
                if wallet not in buf["wallets"]:
                    buf["wallets"].add(wallet)
                    buf["total"] += sol_amount
                    buf["last"] = now

                    if len(buf["wallets"]) == 2:
                        send_telegram(
                            f"🔥 MULTI DETECTED\n\nMint:\n{mint}\nWallets: 2\nTotal: {buf['total']:.2f} SOL"
                        )
                    else:
                        send_telegram(
                            f"♻️ MULTI UPDATE\n\nMint:\n{mint}\nWallets: {len(buf['wallets'])}\nTotal: {buf['total']:.2f} SOL"
                        )

    return jsonify({"ok": True})


@app.route("/test")
def test():
    send_telegram("✅ bot alive")
    return "ok"
