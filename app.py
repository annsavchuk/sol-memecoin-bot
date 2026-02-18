import os
import time
import requests
import threading
import logging
from flask import Flask, request, jsonify
from collections import defaultdict
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# ================= CONFIG (Render Vars) =================
TOKEN_MULTI = os.getenv("TOKEN_MULTI")
CHAT_MULTI = os.getenv("CHAT_MULTI")
TOKEN_SINGLE = os.getenv("TOKEN_SINGLE")
CHAT_SINGLE = os.getenv("CHAT_SINGLE")

if not TOKEN_MULTI: TOKEN_MULTI = os.getenv("TELEGRAM_TOKEN")
if not CHAT_MULTI: CHAT_MULTI = os.getenv("CHAT_ID")

MIN_BUY_SOL = 20.0  
MULTI_MIN_SOL = 5.0 
MULTI_MIN_WALLETS = 3
CLUSTER_LIFETIME = 6 * 3600
SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_KEYWORDS = ["USD", "USDT", "USDC", "SOL", "DAI", "WSOL"]

# ================= STATE =================
clusters = {}
ledger = defaultdict(lambda: {"buy": 0.0, "sell": 0.0})
sent_multi_count = {} 
processed_signatures = {}
lock = threading.Lock()

# ================= ПОВНИЙ СПИСОК ГАМАНЦІВ =================
WALLET_EMOJI = {
    # Твої попередні гаманці
    "CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o": "👽 kentes",
    "5h7yzwmrGoG2BmxNCqNR2EnSv1LWCFo7n6SKSh5ZWkfE": "🖌 307H",
    "4CqecFud362LKgALvChyhj6276he3Sy8yKim1uvFNV1m": "🥴 182 H",
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk": "🦥 GIGO",
    "2C5m99kgdKkiwZCm5qLjpLXrrKAuz1FtM3GoenWkSD8w": "👠 478 H",
    "3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV": "🦜 Bastille",
    "F7KSBM7SVVYUczJTCLpLJFPDEBrmrfi9ZiGru1BzAuwi": "🚄 WolfyXBT",
    "Bpk7VVctpzXYx4BuPnZzs3VSSAWSAQJVq9VufFAq5p6b": "📏 337H",
    "73LnJ7G9ffBDjEBGgJDdgvLUhD5APLonKrNiHsKDCw5B": "🤪 Waddles",
    "HdxkiXqeN6qpK2YbG51W23QSWj3Yygc1eEk2zwmKJExp": "🛶 42H",
    "G5nxEXuFMfV74DSnsrSatqCW32F34XUnBeq3PfDS7w5E": "🎾 72H",
    "FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke": "🧪 Radiance",
    "5B79fMkcFeRTiwm7ehsZsFiKsC7m7n1Bgv9yLxPp9q2X": "🐮 bandit",
    "Ez2jp3rwXUbaTx7XwiHGaWVgTPFdzJoSg8TopqbxfaJN": "🍂 +$313k",
    "GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65": "🤑 latuche",
    "G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC": "📱 clukz",
    "EjaMRoxyHFSLdMtRtXLtinT96mTHhEdp9jubVubwWtxr": "🦋 ОЛД",
    "A2B76kth3LZB7GK6dSzRcZBYNWsn2K6fCWyKVXBFqKx4": "🥩 252H",
    "HYWo71Wk9PNDe5sBaRKazPnVyGnQDiwgXCFKvgAQ1ENp": "🐑 268H",
    "DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC": "🛷 362 H",
    "BQVz7fQ1WsQmSTMY3umdPEPPTm1sdcBcX9sP7o6kPRmB": "🦀 +41.9K",
    "4gLZztSiwUnQtbqzc6sJrTjfgA5RCweHgokiLgEWPn3u": "🦍 +$168К",
    "8rvAsDKeAcEjEkiZMug9k8v1y8mW6gQQiMobd89Uy7qR": "🎰 casino",
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm": "🦩 gake",
    "AEtL29wgARtujVynpgoDtUMLvM7NmZ6WALcjD2NjU8Dk": "🛢 +$166К КИТ",
    "3BLjRcxWGtR7WRshJ3hL25U3RjWr5Ud98wMcczQqk4Ei": "🙊 Sebastian",
    "77n6X7LtGy5AZprsvjZu1eaekJpxqLeVRZLPJZdBYyg9": "⭐ 242Н",
    "BCagckXeMChUKrHEd6fKFA1uiWDtcmCXMsqaheLiUPJd": "🦹 &dv",
    "6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC": "⛷ 184Н",
    "8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs": "🍶 big bags",
    "AeLaMjzxErZt4drbWVWvcxpVyo8p94xu5vrg41eZPFe3": "😡 simle",
    "GrXjXop95XkVPYJafDJNCLFzK9K8LkpopxYcgUUn2H87": "🦁 NEW-189",
    "mW4PZB45isHmnjGkLpJvjKBzVS5NXzTJ8UDyug4gTsM": "🐺 igndex",
    "JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN": "🍃 WEST",
    "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": "🍍 254Н",
    "53BnNc49Ajgstciq3CRoyxuBpkkW1r8pgPyvr7JGYnsh": "👾 Monki",
    "7aMgK5L4qEQ8Nyv6ZzhZi2B82NSSRnwb2NGJnNagA46D": "🍿 70%+66к",
    "J6TDXvarvpBdPXTaTU8eJbtso1PUCYKGkVtMKUUY8iEa": "🧂 +$115к",
    "4SbDMrX8Zfj7qZtRKTBSQEavPkc7BP1kiJfT2f3dn8RL": "🦈 АКУЛА",
    "8MaVa9kdt3NW4Q5HyNAm1X5LbR8PQRVDc1W8NMVK88D5": "🏖 Daumen",
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
    "8PWPhnXh7P7bwoinAavyqsnU33H67x9wkRCxyAWibGD8": "🐽 ? -60%",

    # НОВІ ГАМАНЦІ (додано зараз)
    "34ZEH778zL8ctkLwxxERLX5ZnUu6MuFyX9CWrs8kucMw": "⚓ 111к",
    "CueDkwDYr8ZXRwMseprUpCqsz1Zj1VgLnZNRFyQHkfwZ": "7️⃣ 284Н",
    "3in1nAQoJdnTZsYdmgVfJFLrRR1EoE3HVjyVnZVTMULV": "🦃 279К",
    "HuP4RYp6ZRmhjikmbaHqzNwA71JoQ7oqQMHEZHUWQ4Rb": "⛱ 214",
    "M5Q1hFKopMr2DyNabEkrgoh6tGaF6z6NVQZ5SGUPss8": "🪓 Wallet 159",
    "DMqibTACAF4piJjA92Kuim7pxzuNGFizmuZ5KTtttnx8": "🥪 Sandwich/DEX",
    "CdFHmaj37EtjgRqvyt6vZqoA9tuMSvKLSmbgpuV6ejaP": "💊 442H",
    "F9meywQee74tqAKQvDb4Q9bon7y2XLNwUyFYUNEQUto9": "🏆 Top",
    "2RssnB7hcrnBEx55hXMKT1E7gN27g9ecQFbbCc5Zjajq": "🥴 mostache",
    "DiddyP7tSoS5e26zzy43QVfgTQ3dJ8ZyLibC3uPAAwQk": "🧙 DiddyP",
    "FhLmFRG4iUAN48jXkuEc2fAz9E9ZUbZuW2my7g8TFvsC": "🛒 Wallet 110",
    "ERgtHKpakjFBtcgrh4abzpqFCQKsMdM7QXdE1sfafrWU": "🏅 361Н",
    "Gf9XgdmvNHt8fUTFsWAccNbKeyDXsgJyZN8iFJKg5Pbd": "🦓 10H",
    "BZi5L1mCmVjXdUmeCRQWfKvuWqXakmRYQPFpmS559hD1": "⌛ 118Н",
    "99i9uVA7Q56bY22ajKKUfTZTgTeP5yCtVGsrG9J4pDYQ": "🥺 Zrool",
    "GjBhR6AY2h8d9rg3xrnQpSYRgK57eAnJs8agYFCkA1qM": "🍯 +$93.6K",
    "87MZqjjJgpuFvaU8GyQJKbZGnCFFhX82qAjBGLRXPfcn": "🥁 Nyhrox",
    "pndujwi7BeaRRenYHSShyNQXAdBNEzKDR5jgzbheJFT": "🍺 Unknown",
    "Gq1RQQcvbZu9Ud2wVRy6Krh9RsS1ZYbLBsBuMuvCgyRU": "🌽 Corn",
    "9ZzjXiwkGRDBwVHJitfx8AmnN2YUbnqW6M1tH38juEeJ": "🎉 NEW-321",
    "9HCTuTPEiQvkUtLmTZvK6uch4E3pDynwJTbNw6jLhp9z": "🎡 Wallet 236",
    "DgJxxRStmjsuK1EbPBuVuH7cd68XHKUNV33aeoUfS8ai": "🔍 364Н",
    "HRFekhACsTUj9tRNHR8VfgBSYZp4BodaQwrqfpSePkMT": "👹 +$103K",
    "HtucFepgUkMpHdrYsxMqjBNN6qVBdjmFaLZneNXopuJm": "🥵 Qaunt",
    "J8fYZbmCnAL5WByigxqoum1disKUrZbsAmupfkXMvrmw": "🏁 Wallet 203",
    "BiNp5o3D1NDX4U67wbdvq9nTZUmDoiMRMbNn4dJB2rP9": "🐹 365Н",
    "C3nLTNMK6Ao1s3J1CQhv8GbT3NoMmifWoi9PGEcYd9hP": "👮 $57.7K",
    "8fSnLTnRViK83dDesivTsPx2wiRhwti9xoafeMGjEyLJ": "🎗️ 27H",
    "BC8yiFFQWFEKrEEj75zYsuK3ZDCfv6QEeMRif9oZZ9TW": "🥟 Dumpling",
    "HEW8TmjdtJmAeMWZYG2pZd97FwZybtvJMkFjJmqMz64E": "⛸️ Skates",
    "BHREKFkPQgAtDs8Vb1UfLkUpjG6ScidTjHaCWFuG2AtX": "🎺 Trumpet",
    "9jyqFiLnruggwNn4EQwBNFXwpbLM9hrA4hV59ytyAVVz": "😁 NACH",
    "xXpRSpAe1ajq4tJP78tS3X1AqNwJVQ4Vvb1Swg4hHQh": "🪀 aloh",
    "GybhvUZzTq4qYBc292dz4HE4oQPZJGC9xGJdEH9uYeHK": "⛺ КИТ",
    "9yYya3F5EJoLnBNKW6z4bZvyQytMXzDcpU5D6yYr4jqL": "🥕 loopierr",
    "A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL": "🛠️ Wallet 88",
    "929fdCX5PbGr7rxrUb7GEyVbxka9WXszGkzHrnnCZ58m": "🔱 Trident",
    "ApRnQN2HkbCn7W2WWiT2FEKvuKJp9LugRyAE1a9Hdz1": "🌐 S-Network",
    "3ZsXXbXheMS2D6D6RRuJhERwh82aTgLy2JwFv6PRc4bM": "🍀 Clover",
    "BtMBMPkoNbnLF9Xn552guQq528KKXcsNBNNBre3oaQtr": "🌠 NEW-210",
    "3h65MmPZksoKKyEpEjnWU2Yk2iYT5oZDNitGy5cTaxoE": "🚢 Wallet 13",
    "DKgvpfttzmJqZXdavDwTxwSVkajibjzJnN2FA99dyciK": "🦆 167H",
    "FSvK6sxyLje1A8V7pbXWyroqyFmN41j5oseDCBHjTXL4": "🧢 NEW-305",
    "8deJ9xeUvXSJwicYptA9mHsU2rN2pDx37KWzkDkEXhU6": "👷 Cooker",
    "G1pRtSyKuWSjTqRDcazzKBDzqEF96i1xSURpiXj3yFcc": "🌺 87Н",
    "286CHN57Km41GsAnDv866WKd6YB6HPSjFgF4rGDJTRLf": "🐼 NEW-50",
    "6T8Yr9DUUS2R8GHevaeaZcoxA1Jku51ZBkmcM7NaZiNE": "🌭 306Н",
    "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": "🐘 23Н",
    "BH84Uo2YAnyWRUWeWyfFzttRmE51V682xUaD6NrLHM88": "🔑 100Н",
    "GwyG5FQRNtY1faXYWdTLbcDNZTyW5d2Z63o1UiMUDQDT": "🥨 Pretzel"
}

# ================= HELPERS =================
def short(addr): return f"{addr[:4]}...{addr[-4:]}"
def emoji(w): return WALLET_EMOJI.get(w, "🔹")

def hold_percent(wallet, mint):
    with lock:
        b = ledger[(wallet, mint)]["buy"]
        s = ledger[(wallet, mint)]["sell"]
    if b <= 0: return 0
    return max(0, int(((b - s) / b) * 100))

def format_mc(mc):
    if not mc: return "N/A"
    return f"${mc/1_000_000:.2f}M" if mc >= 1_000_000 else f"${mc/1000:.1f}K"

@lru_cache(maxsize=2000)
def get_symbol(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=5).json()
        if r.get("pairs"): return r["pairs"][0]["baseToken"]["symbol"]
    except: pass
    return mint[:6]

def get_market(mint):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=5).json()
        if not r.get("pairs"): return 0, None
        p = next((x for x in r["pairs"] if x.get("chainId")=="solana"), r["pairs"][0])
        return p.get("fdv",0), p.get("pairAddress")
    except: return 0, None

def build_axiom(mint, pair):
    return f"https://axiom.trade/meme/{pair if pair else mint}?chain=sol"

def send_to_bot(token, chat_id, text, url=None):
    if not token or not chat_id: return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if url: payload["reply_markup"] = {"inline_keyboard": [[{"text": "AXIOM", "url": url}]]}
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=8)
    except Exception as e: logging.error(f"TG Error: {e}")

# ================= STARTUP =================
def startup():
    time.sleep(5)
    send_to_bot(TOKEN_MULTI, CHAT_MULTI, "✅ Multi-Bot підключено (v5.1 з новими гаманцями)")
    send_to_bot(TOKEN_SINGLE, CHAT_SINGLE, "✅ Whale-Bot підключено (v5.1 з новими гаманцями)")

threading.Thread(target=startup).start()

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    txs = request.json
    if not isinstance(txs, list): return jsonify(ok=True)
    now = time.time()

    for tx in txs:
        sig = tx.get("signature")
        if not sig: continue

        with lock:
            if sig in processed_signatures: continue
            processed_signatures[sig] = now

        wallet = tx.get("feePayer")
        if not wallet: continue

        net_sol = 0
        for acc in tx.get("accountData", []):
            if acc.get("account")==wallet:
                net_sol = acc.get("nativeBalanceChange",0)/1e9
        
        sol_abs = abs(net_sol)
        if sol_abs <= 0.05: continue

        bought_mint = None
        for t in tx.get("tokenTransfers",[]):
            mint = t.get("mint")
            if mint==SOL_MINT: continue
            if t.get("toUserAccount")==wallet:
                with lock: ledger[(wallet,mint)]["buy"]+=sol_abs
                bought_mint = mint
            elif t.get("fromUserAccount")==wallet:
                with lock: ledger[(wallet,mint)]["sell"]+=sol_abs

        if not bought_mint: continue
        symbol = get_symbol(bought_mint)
        if any(x in symbol.upper() for x in STABLE_KEYWORDS): continue

        # --- WHALES (20+ SOL) ---
        if sol_abs >= MIN_BUY_SOL:
            mc, pair = get_market(bought_mint)
            ax_u = build_axiom(bought_mint, pair)
            txt_w = (f"🐳 <b>WHALE BUY {symbol}</b>\n\n"
                     f"{emoji(wallet)} {short(wallet)}\n"
                     f"└ <b>{sol_abs:.2f} SOL</b> | MC {format_mc(mc)}\n"
                     f"Hold: 👊 {hold_percent(wallet, bought_mint)}%\n\n"
                     f"<code>{bought_mint}</code>")
            send_to_bot(TOKEN_SINGLE, CHAT_SINGLE, txt_w, ax_u)

        # --- MULTI BUY ---
        if sol_abs >= MULTI_MIN_SOL:
            with lock:
                if bought_mint not in clusters or now - clusters[bought_mint]["first_ts"] > CLUSTER_LIFETIME:
                    clusters[bought_mint] = {"wallets": {}, "total": 0.0, "first_ts": now}
                
                cl = clusters[bought_mint]
                if wallet not in cl["wallets"]:
                    cl["wallets"][wallet] = sol_abs
                    cl["total"] += sol_abs
                    w_count = len(cl["wallets"])
                    
                    last_sent = sent_multi_count.get(bought_mint, {"count": 0})["count"]
                    if w_count >= MULTI_MIN_WALLETS and w_count > last_sent:
                        sent_multi_count[bought_mint] = {"count": w_count, "ts": now}
                        snapshot = {"total": cl["total"], "wallets": cl["wallets"].copy()}
                        
                        def send_m(m, snap, count, sym):
                            _, pr = get_market(m)
                            ax_multi = build_axiom(m, pr)
                            txt_m = f"‼️ 🟢 <b>MULTI BUY {sym}</b>\n\n{count} wallets | {snap['total']:.2f} SOL\n\n"
                            for wal, amt in snap["wallets"].items():
                                txt_m += f"{emoji(wal)} {short(wal)} — <b>{amt:.2f} SOL</b>\n"
                            txt_m += f"\n<code>{m}</code>"
                            send_to_bot(TOKEN_MULTI, CHAT_MULTI, txt_m, ax_multi)
                        
                        threading.Thread(target=send_m, args=[bought_mint, snapshot, w_count, symbol]).start()

    return jsonify(ok=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
