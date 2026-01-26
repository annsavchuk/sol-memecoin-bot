import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HELIUS_KEY = os.getenv("HELIUS_KEY")

MIN_SINGLE = 20
MIN_MULTI = 5
MULTI_WALLETS = 3
CLUSTER_TTL = 21600
WALLET_WINDOW = 60

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLES = {"USDC", "USDT", "USD", "USD1", "SOL"}

# ==== EMOJI MAP ====
WALLET_EMOJI = {
    "As7HjL7dzzvbRbaD3WCun47robib2kmAKRXMvjHkSMB5": "🍡",
    "6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC": "⛷️",
    "Cvmo...dQ97": "👑"
}

multi_clusters = {}
wallet_clusters = {}

# ===== TELEGRAM =====
def send_telegram(text, button=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if button:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "AXIOM", "url": button}]]
        }
    requests.post(url, json=payload, timeout=10)

# ===== TOKEN INFO =====
def token_info(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=10).json()
        for p in r.get("pairs", []):
            if p.get("chainId") == "solana":
                symbol = p["baseToken"]["symbol"]
                mc = p.get("fdv")
                mc = f"${mc/1_000_000:.2f}M" if mc else "N/A"
                pair = p.get("pairAddress")
                link = f"https://axiom.trade/meme/{pair}?chain=sol" if pair else None
                return symbol, mc, link
    except:
        pass
    return mint[:6], "N/A", None

# ===== FORMATTERS =====
def format_multi(symbol, data, mc, mint):
    txt = f"""‼️ 🟢 <b>MULTI BUY {symbol}</b>
Multi preset 1

{len(data['wallets'])} wallets bought {symbol} in the last 6 hours!
Total: {data['total']:.2f} SOL

"""
    for w in data["wallets"]:
        e = WALLET_EMOJI.get(w, "🔹")
        short = f"{w[:4]}...{w[-4:]}"
        txt += f"{e} {short}\n└ {data['per_wallet'][w]:.2f} SOL | MC {mc}\n"

    seen = int(time.time() - data["first_seen"])
    txt += f"\n#{symbol} | MC: {mc} | Seen: {seen}s\n{mint}"
    return txt

def format_buy(symbol, wallet, sol, mc, txs, secs, mint):
    e = WALLET_EMOJI.get(wallet, "👛")
    return f"""🟢 <b>BUY {symbol}</b>

{e} {wallet[:4]}...{wallet[-4:]}
💰 {sol:.2f} SOL
🔁 ({txs} tx in {secs}s)
📊 MC: {mc}

{mint}"""

# ===== WEBHOOK =====
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

        sol = sol_spent / 1e9
        if sol < MIN_MULTI: continue

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint == SOL_MINT: continue

            symbol, mc, axiom = token_info(mint)
            if symbol.upper() in STABLES: continue

            # === wallet cluster ===
            wc = wallet_clusters.get((wallet, mint))
            if not wc or now - wc["first"] > WALLET_WINDOW:
                wallet_clusters[(wallet, mint)] = {"first": now, "count": 1, "total": sol}
            else:
                wc["count"] += 1
                wc["total"] += sol
                if wc["total"] >= MIN_SINGLE:
                    send_telegram(format_buy(symbol, wallet, wc["total"], mc, wc["count"], int(now-wc["first"]), mint), axiom)

            # === multi cluster ===
            cluster = multi_clusters.get(mint)
            if not cluster or now - cluster["first_seen"] > CLUSTER_TTL:
                multi_clusters[mint] = {
                    "wallets": {wallet},
                    "per_wallet": {wallet: sol},
                    "total": sol,
                    "first_seen": now
                }
            else:
                if wallet not in cluster["wallets"] and sol >= MIN_MULTI:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = sol
                    cluster["total"] += sol
                    if len(cluster["wallets"]) >= MULTI_WALLETS:
                        send_telegram(format_multi(symbol, cluster, mc, mint), axiom)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
