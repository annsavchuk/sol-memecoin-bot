import os
import time
import requests
import threading
from flask import Flask, request, jsonify
from collections import defaultdict
from functools import lru_cache

app = Flask(__name__)

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_BUY_SOL = 20           # Для Ordinary Buy
MULTI_MIN_SOL = 5          # Поріг для Multi Buy
MULTI_MIN_WALLETS = 3      # Кількість гаманців для Multi
AGG_WINDOW = 60            # Вікно агрегації секунд
CLUSTER_LIFETIME = 6 * 3600 # 6 годин (час життя сигналу та кулдаун)

STABLE_KEYWORDS = ["USD", "USDT", "USDC", "SOL", "DAI"]
SOL_MINT = "So11111111111111111111111111111111111111112"

# ================= STATE =================
wallet_agg = {}          # (wallet, mint) -> {amount, first_ts}
clusters = {}            # mint -> {wallets, total, first_ts}
ledger = defaultdict(lambda: {"buy": 0.0, "sell": 0.0})

sent_ordinary = {}       # (wallet, mint) -> timestamp (кулдаун 6г)
sent_multi_count = {}    # mint -> {count, timestamp}

WALLET_EMOJI = {
    "CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o": "👽 kentes",
    "5h7yzwmrGoG2BmxNCqNR2EnSv1LWCFo7n6SKSh5ZWkfE": "🖌 307H",
    "4CqecFud362LKgALvChyhj6276he3Sy8yKim1uvFNV1m": "🥴 182 H",
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk": "🦥 GIGO",
    "2C5m99kgdKkiwZCm5qLjpLXrrKAuz1FtM3GoenWkSD8w": "👠 478 H",
    "3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV": "🦜 Bastille",
    "9RTva4wSk8E3EWYc8wtF9V94RUQGkemWtt3i8dUtsA4P": "💤",
    "F7KSBM7SVVYUczJTCLpLJFPDEBrmrfi9ZiGru1BzAuwi": "🚄 WolfyXBT",
    "Bpk7VVctpzXYx4BuPnZzs3VSSAWSAQJVq9VufFAq5p6b": "📏 337H",
    "73LnJ7G9ffBDjEBGgJDdgvLUhD5APLonKrNiHsKDCw5B": "🤪 Waddles",
    "HdxkiXqeN6qpK2YbG51W23QSWj3Yygc1eEk2zwmKJExp": "🛶 42H",
    "G5nxEXuFMfV74DSnsrSatqCW32F34XUnBeq3PfDS7w5E": "🎾 72H",
    "FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke": "🧪 Radiance",
    "5B79fMkcFeRTiwm7ehsZsFiKsC7m7n1Bgv9yLxPp9q2X": "🐮 bandit",
    "Ez2jp3rwXUbaTx7XwiHGaWVgTPFdzJoSg8TopqbxfaJN": "🍂 +$313k",
    "niggerd597QYedtvjQDVHZTCCGyJrwHNm2i49dkm5zS": "🎲 NEW-223",
    "HL3FZ8XWnLnn1HuktmgpNRyFRjuAxWbXNQVj5fPPzZwt": "🧚",
    "GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65": "🤑 latuche",
    "G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC": "📱 clukz",
    "EjaMRoxyHFSLdMtRtXLtinT96mTHhEdp9jubVubwWtxr": "🦋 ОЛД",
    "A2B76kth3LZB7GK6dSzRcZBYNWsn2K6fCWyKVXBFqKx4": "🥩 252H",
    "HYWo71Wk9PNDe5sBaRKazPnVyGnQDiwgXCFKvgAQ1ENp": "🐑 268H",
    "7mGZh58meFf8xsES37bc2hdffEmh8aTDcB2i725Zivyg": "🎷",
    "DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC": "🛷 362 H",
    "BQVz7fQ1WsQmSTMY3umdPEPPTm1sdcBcX9sP7o6kPRmB": "🦀 +41.9K",
    "4gLZztSiwUnQtbqzc6sJrTjfgA5RCweHgokiLgEWPn3u": "🦍 +$168К",
    "8rvAsDKeAcEjEkiZMug9k8v1y8mW6gQQiMobd89Uy7qR": "🎰 casino",
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm": "🦩 gake",
    "AEtL29wgARtujVynpgoDtUMLvM7NmZ6WALcjD2NjU8Dk": "🛢 +$166К КИТ",
    "242p259rfsb9J3X3mhnWw35UM2hfMDg14G47CQ66s9ZW": "💨 NEW-3",
    "2HWT2KLLdN2wxYTqdSuko5SBzg2SEJASgV4GE2tD7TML": "🏗 164Н",
    "76ZUBj1JLz7arTVHSRJok5oSTEqDuVBgySFMVHtzxzZc": "❓ +$87.1К",
    "3BLjRcxWGtR7WRshJ3hL25U3RjWr5Ud98wMcczQqk4Ei": "🙊 Sebastian",
    "77n6X7LtGy5AZprsvjZu1eaekJpxqLeVRZLPJZdBYyg9": "⭐ 242Н",
    "BCagckXeMChUKrHEd6fKFA1uiWDtcmCXMsqaheLiUPJd": "🦹 &dv",
    "6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC": "⛷ 184Н",
    "8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs": "🍶 big bags",
    "AeLaMjzxErZt4drbWVWvcxpVyo8p94xu5vrg41eZPFe3": "😡 simle",
    "GrXjXop95XkVPYJafDJNCLFzK9K8LkpopxYcgUUn2H87": "🦁 NEW-189",
    "mW4PZB45isHmnjGkLpJvjKBzVS5NXzTJ8UDyug4gTsM": "🐺 igndex",
    "XXXXXahGswEH6i3Czn19XbGxQrobJoY1TYJegPxp3ex": "🦜 +$73.1к",
    "JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN": "🍃 WEST",
    "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": "🍍 254Н",
    "53BnNc49Ajgstciq3CRoyxuBpkkW1r8pgPyvr7JGYnsh": "👾 Monki",
    "4nvNc7dDEqKKLM4Sr9Kgk3t1of6f8G66kT64VoC95LYh": "🐌 а",
    "7aMgK5L4qEQ8Nyv6ZzhZi2B82NSSRnwb2NGJnNagA46D": "🍿 70%+66к",
    "J6TDXvarvpBdPXTaTU8eJbtso1PUCYKGkVtMKUUY8iEa": "🧂 +$115к",
    "4SbDMrX8Zfj7qZtRKTBSQEavPkc7BP1kiJfT2f3dn8RL": "🦈 АКУЛА",
    "8MaVa9kdt3NW4Q5HyNAm1X5LbR8PQRVDc1W8NMVK88D5": "🏖 Daumen",
    "CLegS2MSiCsBksVazCg4Y7Gz3NqeBK21QyvzK4Q7S168": "🐝 NEW-13",
    "EQKeA12n4hvs4GhHmdcTMUSkUDF3aurw6zjLXogsw7Sk": "🥥 +$91к",
    "9WyrxBxc6kf8fq1UfmTTtCC7UfBmEGhQkDuWjxoHfvb7": "🚜 346Н",
    "Fh3kfdQGDwzpiiME3X3h6dsbayd3ufrfP3GrdmJ7LKJT": "🗜 +$41.2к",
    "6TbDFs2dkHETrRWVbheiC11bwg7EWLDgszsCADF1ML1b": "🐙 +$42к",
    "As7HjL7dzzvbRbaD3WCun47robib2kmAKRXMvjHkSMB5": "🍡 Скальпер3",
    "HPg7D2urG2B4z2BwKkS8z5HEwRRDKbtmYnAE31oCWzjL": "🎪 +$46к",
    "9rYDSfpA5pLWZakvBSKW5xJAktwDvAQ6m5VDeY4reF4M": "🐣 +95к",
    "5fprK2GKVWvrLTH6QzfmsNnFx4XJSFHc9Da7DDMshqbK": "⛺ NEW-96",
    "Fk9gqZHciE4HKonoeVuF5AHgU8WJZPuuvm1HehSxmRJQ": "🍐 452Н",
    "G3g1CKqKWSVEVURZDNMazDBv7YAhMNTjhJBVRTiKZygk": "🗼 insider",
    "2kv8X2a9bxnBM8NKLc6BBTX2z13GFNRL4oRotMUJRva9": "👻 Gh0stee",
    "FxSuDZSxfouRxKH8LqGUHaecvQTrUNUvh9hk3HRAXiGa": "💋 +70к",
    "BJXjRq566xt66pcxCmCMLPSuNxyUpPNBdJGP56S7fMda": "📆 NEW-560",
    "FRa5xvWrvgYBHEukozdhJPCJRuJZcTn2WKj2u6L75Rmj": "📨 206H",
    "BLhQ4fWgkNAJ4MWXSdXaTnxwZxwHh7QTnMQb6i3Z2QYy": "🌙 90Н",
    "63oQYEauMBFyaGQ69CNkwXFzCvdkFxdPaxGKYx72Tedb": "🎉 120Н",
    "2HpvvY7TcbSdr8uNrDBUyEvbD9mcjg4ssmWQFcQcwJap": "🦊 NEW-199",
    "DsqRyTUh1R37asYcVf1KdX4CNnz5DKEFmnXvgT4NfTPE": "🍗 Classic",
    "EPFDmjJKBX1JrHHpzWRﬀZQv6jeZuo6o3g6FoeKJG5Ha": "🐆 447Н",
    "5owZXjEe27wZTRevqRUETwia3EctJiaYtKhpqmPzWHuj": "🎨 +$90.8к",
    "52YXFG9ksGps7P9ZSDLK79f9Hpa5ihR24w6dkikW5aEB": "👗 49%-30к",
    "8Hw9X9UwBso7Sp2CFnEEeUGW8pGDj9wghc78ccWFZWpU": "💨 +50k",
    "7SDs3PjT2mswKQ7Zo4FTucn9gJdtuW4jaacPA65BseHS": "😀 Insentos",
    "CW6XezzEftYw4aALKo96x6oudqBZ3sfVXrfF23hAezdX": "🦴 295H",
    "EJvokC7vFEubsdEmJX3do1FgfwdUSDYZKGVa5MMs2isA": "🍄 +40к",
    "8eioZubsRjFkNEFcSHKDbWa8MkpmXMBvQcfarGsLviuE": "🍔 +90к",
    "BKT1dCmc72rpsMExWooyTNqs2Qh6MeYMYX68B7JjqdLN": "🪕 +78К",
    "BXAWg4JbaeyvAHpiyYQ3Xr3bUh6FsyDHwwSkB5dmyGF": "👺 ?",
    "2rWMzY58HAvhR4KByBBtuYohptK1xikRSRHPKfJphcQS": "🔦 ame to track",
    "AGqjivJr1dSv73TVUvdtqAwogzmThzvYMVXjGWg2FYLm": "🏐 +$47K?",
    "F5jWYuiDLTiaLYa54D88YbpXgEsA6NKHzWy4SN4bMYjt": "🎹 NEW-545",
    "525LueqAyZJueCoiisfWy6nyh4MTvmF4X9jSqi6efXJT": "🍙 joji",
    "HYMmhz7YBGHLtcvULf2UJSb7Du8p6XFHC3wB3CVeoHm7": "🎋 +$93.5K",
    "2BSwyjCDsxVEXf7DNaqt8ySoaodfuufEpFTxifFHSrsV": "✂ ?2",
    "4M5wSoZyfRsLMHJ2UGuUHYHQ2a5Q72Q7FnGKAS54fCC1": "🕸 +50К",
    "RFSqPtn1JfavGiUD4HJsZyYXvZsycxf31hnYfbyG6iB": "✌ 2",
    "Cvmo9SmWvBabC6ssW5uwThNKWipYJ6UUycBf4dibdQ97": "👠 +$275K",
    "9EyPAMyQvXaUWFxd2uQHvG8vpkKs33YdXvDvwmRXrUiH": "🍬 +$102K",
    "7VBTpiiEjkwRbRGHJFUz6o5fWuhPFtAmy8JGhNqwHNnn": "🐲 Brox",
    "4jSmEmBkuBi1JxZHM1khkf57xPR2oW1EnkRxqehq1cSK": "🎸 Wallet 199",
    "FTkq9ze7Q5X6gVoZ2X6RxbFqoKuzuQbzvWFTsw544cDL": "🔧 +$54.7K",
    "Gmh3Wt423pU6GsS3FQyZjknifnAFW7g3J8HhbF2TrbZL": "🔪 Скальпер2",
    "BTf4A2exGK9BCVDNzy65b9dUzXgMqB4weVkvTMFQsadd": "🐯 LEV",
    "Av3xWHJ5EsoLZag6pr7LKbrGgLRTaykXomDD5kBhL9YQ": "🏋 YOLO",
    "86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD": "🐕 publix",
    "86ssNTYmFVux4NABe22hjjicVsgLzaNfgQzLa1ScicPg": "✏ ++",
    "719sfKUjiMThumTt2u39VMGn612BZyCcwbM5Pe8SqFYz": "💻 FASHR",
    "3tc4BVAdzjr1JpeZu6NAjLHyp4kK3iic7TexMBYGJ4Xk": "🤡 gnf",
    "FvPEk72M6Lp78idz5fbgXZijvaRPgXJGkkJs21hBSWJD": "🧩 +50k",
    "AJ6MGExeK7FXmeKkKPmALjcdXVStXYokYNv9uVfDRtvo": "🦝 TIM",
    "CDNt6H6J7ZBWVjyKJmFRjcJAoHa6XKrn2mTLK3DZwnqL": "🥐 +$86.4K",
    "4Degk564qYYcK4hDZikpNcuS4jNgcGH8PGcJuhgJdPoY": "🦠 new-3",
    "7ABz8qEFZTHPkovMDsmQkm64DZWN5wRtU7LEtD2ShkQ6": "🔴 red",
    "BCnqsPEtA1TkgednYEebRpkmwFRJDCjMQcKZMMtEdArc": "🎄 kreo",
    "DEdEW3SMPU2dCfXEcgj2YppmX9H3bnMDJaU4ctn2BQDQ": "🦕 new-72",
    "4Be9CvxqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7t": "🍀 MITH",
    "7wiEWKeG7sFUNh1TgujwCa9cmJtSSE4mNLDde7knjoeE": "🛰 +$32.2K",
    "BXNiM7pqt9Ld3b2Hc8iT3mA5bSwoe9CRrtkSUs15SLWN": "🎧 ABSOL",
    "AUqmxUYP9pmU4JwMhQiDKc2TNUCzxE5SGoikqFuKCLQT": "🎬 +$56.2K",
    "HwAzzsi2NMirgRDs1LeUTLsPENgfL7pBss5ynEpwV7aY": "🐢 NEW-7",
    "3pkY4S76Jw1UDS8Qgz4wD3DxrTxz7QfyC8yTbXJoZcMT": "🦘 Kai",
    "6EDaVsS6enYgJ81tmhEkiKFcb4HuzPUVFZeom6PHUqN3": "🛵",
    "GJyhzLoZAxZHZGPvF3V1wsyGUnoGSQ55n6hN6nHv7W8B": "🏀 LilmoonLambo",
    "7Eio5ydwGrqkcQMcSahAyYgergkSt2PKkzK2Pc8seMEr": "🐈 +$60.8K?",
    "2iCmwtaM14u5XijJ6Wx6pbxSqvvPbvzUVXAhk1B4aEtr": "🥊 251H",
    "GMfBfVi5CAVfVHn3FoGvxQY7aJeYZLwYLZDenZkBGR2p": "🧸 NEW-6",
    "6sqSp6ejH4jxtreZBGB4LYeAwYK4SsKomBKPEf3trL2C": "🛹 +35K",
    "3wZ6MfB1DRUvtozvcptvV1qAhQ5FKj3qpZR4Db45G6jk": "🤑 ?",
    "4jgTN9YNrq4wCqRJ7tRne4u3S7prjGmvuASy2C36fN6y": "✈ 328H",
    "CBaM2xaPdDdhaopd8dD93LJAvextJoPngdKFz8QFP7JD": "📌 NEW-53",
    "6LChaYRYtEYjLEHhzo4HdEmgNwu2aia8CM8VhR9wn6n7": "🤠 assasin.eth",
    "4u3Baa6znzQ6pjQRLii8KV9tRhtNuXCqwVcY3b6nNpaZ": "🍆 +$303",
    "KzxoVgkSDR7xXYKykbLmSBKMdwzGTesZS7Mc2iXkK9u": "📙 1",
    "8qX6LuKeDmR6FLg8HhmFxQHKhJbhx1zmRgoCk5RCmbk5": "🐧 366H",
    "8PWPhnXh7P7bwoinAavyqsnU33H67x9wkRCxyAWibGD8": "🐽 ? -60%"
}

# ================= CLEANUP TASK =================
def memory_cleanup_loop():
    """Очищення застарілих даних кожні 30 хвилин"""
    while True:
        time.sleep(1800)
        now = time.time()
        try:
            # 1. Агрегації (короткострокові)
            expired_agg = [k for k, v in wallet_agg.items() if now - v['first_ts'] > 600]
            for k in expired_agg: del wallet_agg[k]

            # 2. Кластери Multi Buy (6 годин + запас)
            expired_cl = [k for k, v in clusters.items() if now - v['first_ts'] > (CLUSTER_LIFETIME + 3600)]
            for k in expired_cl:
                del clusters[k]
                sent_multi_count.pop(k, None)

            # 3. Кулдаун Ordinary алерів (тепер 6 годин)
            expired_ord = [k for k, ts in sent_ordinary.items() if now - ts > CLUSTER_LIFETIME]
            for k in expired_ord: del sent_ordinary[k]

            # 4. Ledger (очищуємо старі записи купівель, щоб не росла пам'ять)
            if len(ledger) > 5000: ledger.clear()
            
            print(f"🧹 Cleanup complete. Ordinary alerts reset for next waves.")
        except Exception as e:
            print(f"❌ Cleanup error: {e}")

threading.Thread(target=memory_cleanup_loop, daemon=True).start()

# ================= HELPERS =================
def short(addr):
    return f"{addr[:4]}...{addr[-4:]}"

def emoji(wallet):
    return WALLET_EMOJI.get(wallet, "🔹")

def format_mc(mc):
    if not mc or mc == 0: return "N/A"
    if mc >= 1000000: return f"${mc/1000000:.2f}M"
    return f"${mc/1000:.1f}K"

def hold_percent(wallet, mint):
    b = ledger[(wallet, mint)]["buy"]
    s = ledger[(wallet, mint)]["sell"]
    if b <= 0: return 0
    return max(0, int(((b - s) / b) * 100))

def seen(ts):
    d = int(time.time() - ts)
    if d < 60: return f"{d}s"
    if d < 3600: return f"{d//60}m"
    return f"{d//3600}h"

@lru_cache(maxsize=400)
def fetch_token_info(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=6).json()
        if not r.get("pairs"): return mint[:6], 0, None
        p = next((x for x in r["pairs"] if x.get("chainId") == "solana"), r["pairs"][0])
        symbol = p["baseToken"]["symbol"]
        mc = p.get("fdv", 0)
        pair = p.get("pairAddress")
        axiom = f"https://axiom.trade/meme/{pair}?chain=sol" if pair else None
        return symbol, mc, axiom
    except:
        return mint[:6], 0, None

def send_telegram(text, button_url=None):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if button_url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "AXIOM", "url": button_url}]]}
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=8)
    except: pass

# ================= FORMATTERS =================
def format_buy(symbol, mc, wallet, agg, mint):
    return f"""🟢 <b>BUY {symbol}</b>

{emoji(wallet)} {short(wallet)}
└ {agg['amount']:.2f} SOL | MC {format_mc(mc)}
Total hold: 👊 {hold_percent(wallet, mint)}%

#{symbol} | MC: {format_mc(mc)} | Seen: {seen(agg['first_ts'])}
<code>{mint}</code>"""

def format_multi(symbol, mc, cluster, mint):
    txt = f"‼️ 🟢 <b>MULTI BUY {symbol}</b>\nMulti preset 1\n\n"
    txt += f"{len(cluster['wallets'])} wallets bought in 6h!\nTotal: {cluster['total']:.2f} SOL\n\n"
    for w, amt in cluster["wallets"].items():
        txt += f"{emoji(w)} {short(w)}\n└ {amt:.2f} SOL | 👊 {hold_percent(w, mint)}%\n\n"
    txt += f"#{symbol} | MC: {format_mc(mc)} | Seen: {seen(cluster['first_ts'])}\n<code>{mint}</code>"
    return txt

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    txs = request.json
    now = time.time()
    if not isinstance(txs, list): return jsonify(ok=True)

    for tx in txs:
        wallet = tx.get("feePayer")
        if not wallet: continue

        net_sol_change = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet:
                net_sol_change = acc.get("nativeBalanceChange", 0) / 1e9

        sol_abs = abs(net_sol_change)
        if sol_abs <= 0.005: continue 

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint == SOL_MINT: continue

            symbol, mc, axiom = fetch_token_info(mint)
            if any(x in symbol.upper() for x in STABLE_KEYWORDS): continue

            # Бухгалтерія (Hold %)
            is_buy = float(t.get("tokenAmount", 0)) > 0
            if is_buy:
                ledger[(wallet, mint)]["buy"] += sol_abs
            else:
                ledger[(wallet, mint)]["sell"] += sol_abs

            # Тільки для купівель
            if not is_buy: continue

            # --- ORDINARY LOGIC (Кулдаун 6 годин) ---
            key = (wallet, mint)
            if key not in wallet_agg or now - wallet_agg[key]["first_ts"] > AGG_WINDOW:
                wallet_agg[key] = {"amount": sol_abs, "first_ts": now}
            else:
                wallet_agg[key]["amount"] += sol_abs

            if wallet_agg[key]["amount"] >= MIN_BUY_SOL and key not in sent_ordinary:
                send_telegram(format_buy(symbol, mc, wallet, wallet_agg[key], mint), axiom)
                sent_ordinary[key] = now

            # --- MULTI LOGIC (Вікно 6 годин) ---
            if sol_abs >= MULTI_MIN_SOL:
                if mint not in clusters or now - clusters[mint]["first_ts"] > CLUSTER_LIFETIME:
                    clusters[mint] = {"wallets": {}, "total": 0.0, "first_ts": now}
                
                cl = clusters[mint]
                if wallet not in cl["wallets"]:
                    cl["wallets"][wallet] = sol_abs
                    cl["total"] += sol_abs
                    
                    w_count = len(cl["wallets"])
                    last_alert = sent_multi_count.get(mint, {}).get('count', 0)

                    if w_count >= MULTI_MIN_WALLETS and w_count > last_alert:
                        send_telegram(format_multi(symbol, mc, cl, mint), axiom)
                        sent_multi_count[mint] = {'count': w_count, 'ts': now}

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
