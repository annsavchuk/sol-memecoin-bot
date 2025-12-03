from flask import Flask, request
import os, json, requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    
    # Приходять транзакції від Helius → обробляємо
    try:
        account = data["events"][0]["source"]
        amount = data["events"][0]["amount"]
        mint = data["events"][0]["mint"]

        msg = f"🟢 Купівля!\nГаманець: {account}\nСума: {amount} SOL\nМем-коін: {mint}"
        send_message(msg)

    except Exception as e:
        send_message(f"⚠️ Помилка парсингу: {e}")

    return "ok"
