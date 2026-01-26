import os, time, requests
from collections import defaultdict
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== ENV =====
HELIUS_KEY = os.getenv("HELIUS_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"

# ===== CONFIG =====
BUY_MIN_SOL = 20
MULTI_MIN_SOL = 5
MULTI_MIN_WALLETS = 3
MERGE_WINDOW = 60
MULTI_LIFETIME = 21600

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLES = {"USDC", "USDT", "USD1", "USDTt", "USD1tt"}

# ===== WALLET EMOJIS =====
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
single_clusters = {}
multi_tokens = {}

# ===== TELEGRAM =====
def send_telegram(text, button=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode":"HTML"}
    if button:
        payload["reply_markup"]={"inline_keyboard":[[{"text":"AXIOM","url":button}]]}
    requests.post(url,json=payload,timeout=10)

# ===== RPC =====
def rpc(method, params):
    return requests.post(RPC,json={"jsonrpc":"2.0","id":1,"method":method,"params":params}).json()

def get_token_balance(wallet, mint):
    r = rpc("getTokenAccountsByOwner",[wallet,{"mint":mint},{"encoding":"jsonParsed"}])
    total=0
    for v in r.get("result",{}).get("value",[]):
        total+=float(v["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
    return total

def get_total_buys(wallet,mint):
    sigs = rpc("getSignaturesForAddress",[wallet,{"limit":100}])
    total=0
    for s in sigs.get("result",[]):
        tx = rpc("getTransaction",[s["signature"],{"encoding":"jsonParsed"}])
        if not tx.get("result"): continue
        for t in tx["result"]["meta"].get("postTokenBalances",[]):
            if t.get("mint")==mint and t.get("owner")==wallet:
                total+=float(t["uiTokenAmount"]["uiAmount"] or 0)
    return total

# ===== DEX =====
def token_info(mint):
    try:
        r=requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}",timeout=10).json()
        for p in r.get("pairs",[]):
            if p.get("chainId")=="solana":
                mc=p.get("fdv")
                mc = f"${mc/1e6:.2f}M" if mc else "N/A"
                sym=p["baseToken"]["symbol"]
                pair=p.get("pairAddress")
                ax=f"https://axiom.trade/meme/{pair}?chain=sol" if pair else None
                return sym,mc,ax
    except: pass
    return mint[:6],"N/A",None

# ===== FORMAT =====
def fmt_wallet(w): return f"{w[:4]}...{w[-4:]}"
def emoji(w): return WALLET_EMOJI.get(w,"🔹")

def format_block(symbol,mc,seen,mint,rows):
    txt=f"‼️ 🟢 MULTI BUY {symbol}\nMulti preset 1\n\n"
    txt+=f"{len(rows)} wallets bought {symbol} in the last 6 hours!\n"
    txt+=f"Total: {sum(r['sol'] for r in rows):.2f} SOL\n\n"
    for r in rows:
        txt+=f"🔹 {emoji(r['w'])} {fmt_wallet(r['w'])}\n"
        txt+=f"└ {r['sol']:.2f} SOL | MC {mc}\n"
        txt+=f"   Total buy: {r['total']:.2f} | 👊 {r['hold']}%\n\n"
    txt+=f"#{symbol} | MC: {mc} | Seen: {seen}s\n{mint}"
    return txt

# ===== WEBHOOK =====
@app.route("/",methods=["POST"])
def hook():
    txs=request.json
    now=time.time()
    for tx in txs:
        wallet=tx.get("feePayer")
        sol_spent=0
        for a in tx.get("accountData",[]):
            if a.get("account")==wallet and a.get("nativeBalanceChange",0)<0:
                sol_spent=abs(a["nativeBalanceChange"])/1e9
        for t in tx.get("tokenTransfers",[]):
            mint=t.get("mint")
            if not mint or mint==SOL_MINT: continue
            sym,mc,ax=token_info(mint)
            if sym in STABLES: continue

            key=(wallet,mint)
            cl=single_clusters.get(key)
            if cl and now-cl["last"]<MERGE_WINDOW:
                cl["sol"]+=sol_spent
                cl["tx"]+=1
                cl["last"]=now
                continue

            single_clusters[key]={"sol":sol_spent,"tx":1,"last":now}
            if sol_spent>=BUY_MIN_SOL:
                bal=get_token_balance(wallet,mint)
                tot=get_total_buys(wallet,mint)
                hold=int((bal/tot)*100) if tot else 0
                txt=format_block(sym,mc,0,mint,[{"w":wallet,"sol":sol_spent,"total":tot,"hold":hold}])
                send_telegram(txt,ax)

            cluster=multi_tokens.get(mint)
            if not cluster or now-cluster["first"]>MULTI_LIFETIME:
                multi_tokens[mint]={"first":now,"rows":[]}
                cluster=multi_tokens[mint]

            if sol_spent>=MULTI_MIN_SOL:
                bal=get_token_balance(wallet,mint)
                tot=get_total_buys(wallet,mint)
                hold=int((bal/tot)*100) if tot else 0
                cluster["rows"].append({"w":wallet,"sol":sol_spent,"total":tot,"hold":hold})

                if len({r["w"] for r in cluster["rows"]})>=MULTI_MIN_WALLETS:
                    seen=int(now-cluster["first"])
                    txt=format_block(sym,mc,seen,mint,cluster["rows"])
                    send_telegram(txt,ax)
    return jsonify({"ok":True})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000)))
