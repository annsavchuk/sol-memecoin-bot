import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_TX_SOL = 5
MULTI_LIFETIME = 21600
SINGLE_WINDOW = 60

SOL_MINT = "So11111111111111111111111111111111111111112"
BLOCKED = {"usdc","usdt","usd","usd1","usdb","busd","dai","sol"}

multi_tokens = {}
single_buffer = {}

# ===== TELEGRAM =====
def send_telegram(text, mint):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    axiom = f"https://axiom.trade/token/{mint}"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": {
            "inline_keyboard": [[{"text": "AXIOM", "url": axiom}]]
        }
    }
    requests.post(url, json=payload, timeout=10)

# ===== DEX =====
def fetch_pair(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=10).json()
        for p in r.get("pairs", []):
            if p.get("chainId") == "solana":
                return p
    except:
        pass
    return None

def token_info(mint):
    pair = fetch_pair(mint)
    symbol = mint[:6]
    mc = "N/A"

    if pair:
        symbol = pair["baseToken"]["symbol"]
        fdv = pair.get("fdv")
        if fdv:
            mc = f"${fdv/1000:.2f}K"

    return symbol, mc

# ===== FORMAT =====
def format_buy(symbol, wallet, total, txs, delta, mc, mint):
    return f"""🟢 <b>BUY {symbol}</b>

👛 {wallet[:6]}...{wallet[-4:]}
💰 {total:.2f} SOL
🔁 ({txs} tx in {delta}s)
📊 MC: {mc}

{mint}"""

def format_multi(symbol, data, mc, mint):
    txt = f"""‼️ 🟢
