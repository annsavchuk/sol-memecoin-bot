import os, time, requests, threading
from flask import Flask, request, jsonify
from collections import defaultdict

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ===== SETTINGS =====
BUY_MIN_SOL = 20
MULTI_MIN_SOL = 5
MULTI_MIN_WALLETS = 3
TX_BUFFER = 60
MULTI_LIFETIME = 21600
SOL_MINT = "So11111111111111111111111111111111111111112"

STABLE_KEYWORDS = ["usd", "usdt", "usdc", "busd", "eur", "dai"]

# ===== WALLET EMOJI =====
WALLET_EMOJI = {
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
    "niggerd597QYedtvjQDVHZTCCGyJrwHNm2i49dkm5zS": "🎲",
    "HL3FZ8XWnLnn1HuktmgpNRyFRjuAxWbXNQVj5fPPzZwt": "🧚",
    "GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65": "🤑",
    "G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC": "📱",
    "EjaMRoxyHFSLdMtRtXLtinT96mTHhEdp9jubVubwWtxr": "🦋",

    "A2B76kth3LZB7GK6dSzRcZBYNWsn2K6fCWyKVXBFqKx4": "🥩",
    "HYWo71Wk9PNDe5sBaRKazPnVyGnQDiwgXCFKvgAQ1ENp": "🐑",
    "7mGZh58meFf8xsES37bc2hdffEmh8aTDcB2i725Zivyg": "🎷",
    "DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC": "🛷",
    "BQVz7fQ1WsQmSTMY3umdPEPPTm1sdcBcX9sP7o6kPRmB": "🦀",
    "4gLZztSiwUnQtbqzc6sJrTjfgA5RCweHgokiLgEWPn3u": "🦍",
    "8rvAsDKeAcEjEkiZMug9k8v1y8mW6gQQiMobd89Uy7qR": "🎰",
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm": "🦩",
    "AEtL29wgARtujVynpgoDtUMLvM7NmZ6WALcjD2NjU8Dk": "🛢️",
    "242p259rfsb9J3X3mhnWw35UM2hfMDg14G47CQ66s9ZW": "💨",
    "2HWT2KLLdN2wxYTqdSuko5SBzg2SEJASgV4GE2tD7TML": "🏗️",
    "76ZUBj1JLz7arTVHSRJok5oSTEqDuVBgySFMVHtzxzZc": "❓",
    "3BLjRcxWGtR7WRshJ3hL25U3RjWr5Ud98wMcczQqk4Ei": "🙊",
    "77n6X7LtGy5AZprsvjZu1eaekJpxqLeVRZLPJZdBYyg9": "⭐️",
    "BCagckXeMChUKrHEd6fKFA1uiWDtcmCXMsqaheLiUPJd": "🦹‍♀️",
    "6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC": "⛷️",
    "8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs": "🍶",
    "AeLaMjzxErZt4drbWVWvcxpVyo8p94xu5vrg41eZPFe3": "😡",
    "GrXjXop95XkVPYJafDJNCLFzK9K8LkpopxYcgUUn2H87": "🦁",
    "mW4PZB45isHmnjGkLpJvjKBzVS5NXzTJ8UDyug4gTsM": "🐺",

    "JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN": "🍃",
    "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": "🍍",
    "53BnNc49Ajgstciq3CRoyxuBpkkW1r8pgPyvr7JGYnsh": "👾",
    "4nvNc7dDEqKKLM4Sr9Kgk3t1of6f8G66kT64VoC95LYh": "🐌",
    "7aMgK5L4qEQ8Nyv6ZzhZi2B82NSSRnwb2NGJnNagA46D": "🍿",
    "J6TDXvarvpBdPXTaTU8eJbtso1PUCYKGkVtMKUUY8iEa": "🧂",
    "4SbDMrX8Zfj7qZtRKTBSQEavPkc7BP1kiJfT2f3dn8RL": "🦈",
    "8MaVa9kdt3NW4Q5HyNAm1X5LbR8PQRVDc1W8NMVK88D5": "🏖️",
    "EQKeA12n4hvs4GhHmdcTMUSkUDF3aurw6zjLXogsw7Sk": "🥥",
    "BC8yiFFQWFEKrEEj75zYsuK3ZDCfv6QEeMRif9oZZ9TW": "🥟",
    "9WyrxBxc6kf8fq1UfmTTtCC7UfBmEGhQkDuWjxoHfvb7": "🚜",
    "Fh3kfdQGDwzpiiME2X3h6dsbayd3ufrfP3GrdmJ7LKJT": "🗜️",
    "6TbDFs2dkHETrRWVbheiC11bwg7EWLDgszsCADF1ML1b": "🐙",
    "As7HjL7dzzvbRbaD3WCun47robib2kmAKRXMvjHkSMB5": "🍡",
    "HPg7D2urG2B4z2BwKkS8z5HEwRRDKbtmYnAE31oCWzjL": "🎪",
    "9rYDSfpA5pLWZakvBSKW5xJAktwDvAQ6m5VDeY4reF4M": "🐣",
    "5fprK2GKVWvrLTH6QzfmsNnFx4XJSFHc9Da7DDMshqbK": "⛺️",
    "Fk9gqZHciE4HKonoeVuF5AHgU8WJZPuuvm1HehSxmRJQ": "🍐",
    "G3g1CKqKWSVEVURZDNMazDBv7YAhMNTjhJBVRTiKZygk": "🗼",

    "2kv8X2a9bxnBM8NKLc6BBTX2z13GFNRL4oRotMUJRva9": "👻",
    "FxSuDZSxfouRxKH8LqGUHaecvQTrUNUvh9hk3HRAXiGa": "💋",
    "BJXjRq566xt66pcxCmCMLPSuNxyUpPNBdJGP56S7fMda": "📆",
    "FRa5xvWrvgYBHEukozdhJPCJRuJZcTn2WKj2u6L75Rmj": "📨",
    "BLhQ4fWgkNAJ4MWXSdXaTnxwZxwHh7QTnMQb6i3Z2QYy": "🌙",
    "63oQYEauMBFyaGQ69CNkwXFzCvdkFxdPaxGKYx72Tedb": "🎉",
    "2HpvvY7TcbSdr8uNrDBUyEvbD9mcjg4ssmWQFcQcwJap": "🦊",
    "DsqRyTUh1R37asYcVf1KdX4CNnz5DKEFmnXvgT4NfTPE": "🍗",
    "EPFDmjJKBX1JrHHpzWRffZQv6jeZuo6o3g6FoeKJG5Ha": "🐆",
    "5owZXjEe27wZTRevqRUETwia3EctJiaYtKhpqmPzWHuj": "🎨",
    "52YXFG9ksGps7P9ZSDLK79f9Hpa5ihR24w6dkikW5aEB": "👗",
    "B3wagQZiZU2hKa5pUCj6rrdhWsX3Q6WfTTnki9PjwzMh": "🔫",
    "A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL": "🛠️",
    "BiNp5o3D1NDX4U67wbdvq9nTZUmDoiMRMbNn4dJB2rP9": "🐹",
    "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": "🐘",
    "CLegS2MSiCsBksVazCg4Y7Gz3NqeBK21QyvzK4Q7S168": "🐝",
    "8Hw9X9UwBso7Sp2CFnEEeUGW8pGDj9wghc78ccWFZWpU": "💨",
    "8eioZubsRjFkNEFcSHKDbWa8MkpmXMBvQcfarGsLviuE": "🍔",
    "BKT1dCmc72rpsMExWooyTNqs2Qh6MeYMYX68B7JjqdLN": "🪕",
    "BXAWg4JbaeyvAHpiyYQ3Xr3bUh6FsyDHwwSkB5dmyGF": "👺",
}

# ===== STATE =====
tx_buffer = defaultdict(list)
multi_clusters = {}

# ===== TELEGRAM =====
def send_telegram(text, button=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if button:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "AXIOM", "url": button}]]
        }
    requests.post(url, json=payload, timeout=10)

# ===== UTILS =====
def short(addr):
    return f"{addr[:4]}...{addr[-4:]}"

def seen_str(sec):
    if sec < 60: return f"{sec}s"
    return f"{sec//60}m {sec%60}s"

def fetch_pair(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=10).json()
        for p in r.get("pairs", []):
            if p.get("chainId") == "solana":
                return p
    except: pass
    return None

def token_info(mint):
    p = fetch_pair(mint)
    if not p: return mint[:6], "N/A", None, None, 0
    sym = p["baseToken"]["symbol"]
    fdv = p.get("fdv")
    mc = f"${fdv/1_000_000:.2f}M" if fdv and fdv>1e6 else f"${fdv/1000:.2f}K" if fdv else "N/A"
    pair = p.get("pairAddress")
    axiom = f"https://axiom.trade/meme/{pair}?chain=sol" if pair else None
    return sym, mc, axiom, pair, fdv or 0

# ===== FORMAT =====
def format_buy(sym, wallet, data, mc, mint):
    emoji = WALLET_EMOJI.get(wallet, "🔹")
    return f"""🟢 <b>BUY {sym}</b>

{emoji} {short(wallet)}
└ {data['total']:.2f} SOL | MC {mc}
({len(data['txs'])} tx in {int(time.time()-data['first'])}s)

#{sym} | MC: {mc} | Seen: {seen_str(int(time.time()-data['first']))}
{mint}"""

def format_multi(sym, cluster, mc, mint):
    txt = f"""‼️ 🟢 <b>MULTI BUY {sym}</b>
Multi preset 1

{len(cluster['wallets'])} wallets bought {sym} in the last 6 hours!
Total: {cluster['total']:.2f} SOL\n\n"""
    for w in list(cluster["wallets"])[-5:]:
        emoji = WALLET_EMOJI.get(w, "🔹")
        hold = cluster["hold"].get(w, 0)
        txt += f"{emoji} {short(w)}\n└ {cluster['per_wallet'][w]:.2f} SOL | MC {mc}\nTotal buy: {cluster['total_by_wallet'].get(w,0):.2f} SOL | 👊 {hold}%\n\n"
    seen = int(time.time() - cluster["first_seen"])
    txt += f"#{sym} | MC: {mc} | Seen: {seen_str(seen)}\n{mint}"
    return txt

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
            if acc.get("account") == wallet and acc.get("nativeBalanceChange",0)<0:
                sol_spent = abs(acc["nativeBalanceChange"])
                break

        sol = sol_spent / 1e9
        if sol < MULTI_MIN_SOL: continue

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint == SOL_MINT: continue

            sym, mc, axiom, pair, fdv = token_info(mint)
            if any(k in sym.lower() for k in STABLE_KEYWORDS): continue

            key = f"{wallet}|{mint}"
            tx_buffer[key].append((now, sol))
            tx_buffer[key] = [x for x in tx_buffer[key] if now-x[0]<=TX_BUFFER]

            total = sum(x[1] for x in tx_buffer[key])
            first = tx_buffer[key][0][0]

            # SINGLE BUY
            if total >= BUY_MIN_SOL:
                data = {"total": total, "txs": tx_buffer[key], "first": first}
                send_telegram(format_buy(sym, wallet, data, mc, mint), axiom)

            # MULTI
            cluster = multi_clusters.get(mint)
            if not cluster:
                multi_clusters[mint] = {
                    "wallets": {wallet},
                    "per_wallet": {wallet: sol},
                    "total_by_wallet": {wallet: sol},
                    "hold": {wallet: 0},
                    "total": sol,
                    "first_seen": now
                }
            else:
                if wallet not in cluster["wallets"]:
                    cluster["wallets"].add(wallet)
                    cluster["per_wallet"][wallet] = sol
                    cluster["total_by_wallet"][wallet] = sol
                    cluster["total"] += sol

                if len(cluster["wallets"]) >= MULTI_MIN_WALLETS:
                    send_telegram(format_multi(sym, cluster, mc, mint), axiom)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
