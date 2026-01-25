import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================== SETTINGS ==================
MIN_TX_SOL = 5
TX_BUFFER = 60            # 1 wallet → merge tx за 60 сек
MULTI_LIFETIME = 21600   # 6 год
SOL_MINT = "So11111111111111111111111111111111111111112"

STABLE_SYMBOLS = {"USD", "USDT", "USDC", "USD1", "SOL"}

# ================== SMART WALLETS ==================
WALLET_EMOJIS = {
    "CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o": "👽",
    "5h7yzwmrGoG2BmxNCqNR2EnSv1LWCFo7n6SKSh5ZWkfE": "🖌️",
    "4CqecFud362LKgALvChyhj6276he3Sy8yKim1uvFNV1m": "🥴",
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk": "🦥",
    "2C5m99kgdKkiwZCm5qLjpLXrrKAuz1FtM3GoenWkSD8w": "👠",
    "3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV": "🦜",
    "9RTva4wSk8E3EWYc8wtF9V94RUQGkemWtt3i8dUtsA4P": "💤",
    "F7KSBM7SVVYUczJTCLpLJFPDEBrmrfi9ZiGru1BzAuwi": "🚄",
    "Bpk7VVctpzXYx4BuPnZzs3VSSAWSAQJVq9VufFAq5p6b": "📏",
    "73LnJ7G9ffBDjEBGgJDdgvLUhD5APLonKrNiHsKDCw5B": "🤪",
    "HdxkiXqeN6qpK2YbG51W23QSWj3Yygc1eEk2zwmKJExp": "🛶",
    "G5nxEXuFMfV74DSnsrSatqCW32F34XUnBeq3PfDS7w5E": "🎾",
    "FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke": "🧪",
    "5B79fMkcFeRTiwm7ehsZsFiKsC7m7n1Bgv9yLxPp9q2X": "🐮",
    "Ez2jp3rwXUbaTx7XwiHGaWVgTPFdzJoSg8TopqbxfaJN": "🍂",
}

# ================== MEMORY ==================
wallet_buffers = {}   # wallet|mint -> {total, count, first}
multi_tokens = {}    # mint -> cluster

# ================== TELEGRAM ==================
def send_telegram(text, axiom=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if axiom:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "AXIOM", "url": axiom}]]
        }
    requests.post(url, json=payload, timeout=10)

# ================== DEX INFO ==================
def fetch_pair(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=8).json()
        for p in r.get("pairs", []):
            if p.get("chainId") == "solana":
                return p
    except:
        pass
    return None

def format_mc(fdv):
    if not fdv: return "N/A"
    if fdv >= 1_000_000:
        return f"${fdv/1_000_000:.2f}M"
    return f"${fdv/1000:.2f}K"

def token_info(mint):
    pair = fetch_pair(mint)
    if not pair:
        return mint[:6], "N/A", None
    symbol = pair["baseToken"]["symbol"]
    mc = format_mc(pair.get("fdv"))
    pair_id = pair.get("pairAddress")
    axiom = f"https://axiom.trade/meme/{pair_id}?chain=sol" if pair_id else None
    return symbol, mc, axiom

# ================== FORMAT ==================
def short(w): return f"{w[:4]}...{w[-4:]}"
def seen(sec): return f"{sec}s" if sec < 60 else f"{int(sec/60)}m"
def emoji(w): return WALLET_EMOJIS.get(w, "🔹")

def format_buy(symbol, mint, wallet, sol, mc, txc, dur):
    return f"""🟢 <b>BUY {symbol}</b>

🔹 {emoji(wallet)} {short(wallet)}
└ {sol:.2f} SOL | MC {mc}

({txc} tx in {dur}s)

#{symbol} | MC: {mc} | Seen: {seen(dur)}
{mint}"""

def format_multi(symbol, mint, data, mc):
    txt = f"""‼️ 🟢 <b>MULTI BUY {symbol}</b>
Multi preset 1

{len(data['wallets'])} wallets bought {symbol} in the last 6 hours!
Total: {data['total']:.2f} SOL

"""
    for w in list(data["wallets"])[-5:]:
        txt += f"🔹 {emoji(w)} {short(w)}\n└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    s = int(time.time() - data["first_seen"])
    txt += f"\n#{symbol} | MC: {mc} | Seen: {seen(s)}\n{mint}"
    return txt

# ================== WEBHOOK ==================
@app.route("/", methods=["POST"])
def webhook():
    txs = request.json
    if not isinstance(txs, list):
        return jsonify({"ok": True})

    now = time.time()

    for tx in txs:
        wallet = tx.get("feePayer")
        if not wallet: continue

        sol_spent = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet and acc.get("nativeBalanceChange", 0) < 0:
                sol_spent = abs(acc["nativeBalanceChange"])
                break

        sol_amount = sol_spent / 1e9
        if sol_amount < MIN_TX_SOL: continue

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if not mint or mint == SOL_MINT: continue

            symbol, mc, axiom = token_info(mint)
            if symbol.upper() in STABLE_SYMBOLS: continue

            key = f"{wallet}|{mint}"
            buf = wallet_buffers.get(key)

            if not buf:
                wallet_buffers[key] = {"total": sol_amount, "count": 1, "first": now}
            else:
                if now - buf["first"] <= TX_BUFFER:
                    buf["total"] += sol_amount
                    buf["count"] += 1
                else:
                    buf["total"] = sol_amount
                    buf["count"] = 1
                    buf["first"] = now

            buf = wallet_buffers[key]
            dur = int(now - buf["first"])

            cluster = multi_tokens.get(mint)
            if not cluster or now - cluster["first_seen"] > MULTI_LIFETIME:
                multi_tokens[mint] = {
                    "wallets": {wallet},
                    "per_wallet": {wallet: buf["total"]},
                    "total": buf["total"],
                    "first_seen": now
                }
                send_telegram(format_buy(symbol, mint, wallet, buf["total"], mc, buf["count"], dur), axiom)

            else:
                if wallet not in cluster["wallets"]:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = buf["total"]
                    cluster["total"] += buf["total"]

                    if len(cluster["wallets"]) >= 2:
                        send_telegram(format_multi(symbol, mint, cluster, mc), axiom)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
