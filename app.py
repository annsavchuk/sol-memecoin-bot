import os
import time
import requests
import threading
import logging
from flask import Flask, request, jsonify
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
app = Flask(__name__)

# ================= CONFIG =================
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
CHAT_ID           = os.getenv("CHAT_ID")

MIN_BUY_SOL       = 9
MULTI_MIN_SOL     = 5
MULTI_MIN_WALLETS = 3
CLUSTER_LIFETIME  = 6 * 3600
SIGNATURE_TTL     = 600
MIN_MC_USD        = 30_000  # $30K — після міграції

STABLE_SYMBOLS = {"SOL", "WSOL", "USDC", "USDT", "DAI", "USD", "SOLANA"}

STABLE_MINTS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
    "So11111111111111111111111111111111111111112",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",
    "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1",
}

SOL_MINT = "So11111111111111111111111111111111111111112"

# ================= STATE =================
wallet_agg           = {}
clusters             = {}
ledger               = defaultdict(lambda: {"buy": 0.0, "sell": 0.0, "last_ts": 0.0})
sent_ordinary        = {}
sent_multi           = {}
processed_signatures = {}
lock                 = threading.Lock()

# ================= CACHES =================
# symbol_cache[mint] = (symbol, timestamp)
symbol_cache = {}
# ✅ market_cache[mint] = (mc, pair, last_fetch_ts, last_valid_mc, last_valid_pair)
# last_valid_mc/pair — останні валідні дані, НІКОЛИ не затираються нулем
market_cache = {}

SYMBOL_TTL       = 3600
MARKET_TTL       = 30    # як часто робимо новий запит

# ================= WALLET EMOJI =================
WALLET_EMOJI = {
    "BiNp5o3D1NDX4U67wbdvq9nTZUmDoiMRMbNn4dJB2rP9": "🐹 365H",
    "C3nLTNMK6Ao1s3J1CQhv8GbT3NoMmifWoi9PGEcYd9hP": "👮 +$57.7K?",
    "8fSnLTnRViK83dDesivTsPx2wiRhwti9xoafeMGjEyLJ": "🎗 27H",
    "BC8yiFFQWFEKrEEj75zYsuK3ZDCfv6QEeMRif9oZZ9TW": "🥟 ?",
    "HEW8TmjdtJmAeMWZYG2pZd97FwZybtvJMkFjJmqMz64E": "⛸ ?",
    "BHREKFkPQgAtDs8Vb1UfLkUpjG6ScidTjHaCWFuG2AtX": "🎺 &",
    "9jyqFiLnruggwNn4EQwBNFXwpbLM9hrA4hV59ytyAVVz": "😁 NACH",
    "xXpRSpAe1ajq4tJP78tS3X1AqNwJVQ4Vvb1Swg4hHQh": "🪀 aloh",
    "GybhvUZzTq4qYBc292dz4HE4oQPZJGC9xGJdEH9uYeHK": "⛺ КИТ",
    "9yYya3F5EJoLnBNKW6z4bZvyQytMXzDcpU5D6yYr4jqL": "🥕 loopierr",
    "A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL": "🛠 Wallet 88",
    "929fdCX5PbGr7rxrUb7GEyVbxka9WXszGkzHrnnCZ58m": "🔱 +",
    "ApRnQN2HkbCn7W2WWiT2FEKvuKJp9LugRyAE1a9Hdz1": "🌐 S",
    "3ZsXXbXheMS2D6D6RRuJhERwh82aTgLy2JwFv6PRc4bM": "🍀 ?",
    "BtMBMPkoNbnLF9Xn552guQq528KKXcsNBNNBre3oaQtr": "🌠 NEW-210",
    "3h65MmPZksoKKyEpEjnWU2Yk2iYT5oZDNitGy5cTaxoE": "🚢 Wallet 13",
    "DKgvpfttzmJqZXdavDwTxwSVkajibjzJnN2FA99dyciK": "🦆 167H",
    "FSvK6sxyLje1A8V7pbXWyroqyFmN41j5oseDCBHjTXL4": "🧢 NEW-305",
    "8deJ9xeUvXSJwicYptA9mHsU2rN2pDx37KWzkDkEXhU6": "👷 Cooker",
    "G1pRtSyKuWSjTqRDcazzKBDzqEF96i1xSURpiXj3yFcc": "🌺 87H",
    "286CHN57Km41GsAnDv866WKd6YB6HPSjFgF4rGDJTRLf": "🐼 NEW-50",
    "6T8Yr9DUUS2R8GHevaeaZcoxA1Jku51ZBkmcM7NaZiNE": "🌭 306H",
    "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": "🐘 23H",
    "BH84Uo2YAnyWRUWeWyfFzttRmE51V682xUaD6NrLHM88": "🔑 100H",
    "GwyG5FQRNtY1faXYWdTLbcDNZTyW5d2Z63o1UiMUDQDT": "🥨 ?",
    "34ZEH778zL8ctkLwxxERLX5ZnUu6MuFyX9CWrs8kucMw": "⚓ 111k",
    "CueDkwDYr8ZXRwMseprUpCqsz1Zj1VgLnZNRFyQHkfwZ": "7 284H",
    "3in1nAQoJdnTZsYdmgVfJFLrRR1EoE3HVjyVnZVTMULV": "🦃 279K",
    "HuP4RYp6ZRmhjikmbaHqzNwA71JoQ7oqQMHEZHUWQ4Rb": "⛱ 214",
    "M5Q1hFKopMr2DyNabEkrgoh6tGaF6z6NVQZ5SGUPss8": "🪓 Wallet 159",
    "DMqibTACAF4piJjA92Kuim7pxzuNGFizmuZ5KTtttnx8": "🥪",
    "CdFHmaj37EtjgRqvyt6vZqoA9tuMSvKLSmbgpuV6ejaP": "💊 442H",
    "F9meywQee74tqAKQvDb4Q9bon7y2XLNwUyFYUNEQUto9": "🏆",
    "2RssnB7hcrnBEx55hXMKT1E7gN27g9ecQFbbCc5Zjajq": "🥴 mostache",
    "DiddyP7tSoS5e26zzy43QVfgTQ3dJ8ZyLibC3uPAAwQk": "🧙 DiddyP",
    "FhLmFRG4iUAN48jXkuEc2fAz9E9ZUbZuW2my7g8TFvsC": "🛒 Wallet 110",
    "ERgtHKpakjFBtcgrh4abzpqFCQKsMdM7QXdE1sfafrWU": "🏅 361H",
    "Gf9XgdmvNHt8fUTFsWAccNbKeyDXsgJyZN8iFJKg5Pbd": "🦓 10H",
    "BZi5L1mCmVjXdUmeCRQWfKvuWqXakmRYQPFpmS559hD1": "⌛ 118H",
    "99i9uVA7Q56bY22ajKKUfTZTgTeP5yCtVGsrG9J4pDYQ": "🥺 Zrool",
    "GjBhR6AY2h8d9rg3xrnQpSYRgK57eAnJs8agYFCkA1qM": "🍯 +$93.6K",
    "87MZqjjJgpuFvaU8GyQJKbZGnCFFhX82qAjBGLRXPfcn": "🥁 Nyhrox",
    "pndujwi7BeaRRenYHSShyNQXAdBNEzKDR5jgzbheJFT": "🍺 ?",
    "Gq1RQQcvbZu9Ud2wVRy6Krh9RsS1ZYbLBsBuMuvCgyRU": "🌽",
    "9ZzjXiwkGRDBwVHJitfx8AmnN2YUbnqW6M1tH38juEeJ": "🎉 NEW-321",
    "9HCTuTPEiQvkUtLmTZvK6uch4E3pDynwJTbNw6jLhp9z": "🎡 Wallet 236",
    "DgJxxRStmjsuK1EbPBuVuH7cd68XHKUNV33aeoUfS8ai": "🔍 364H",
    "HRFekhACsTUj9tRNHR8VfgBSYZp4BodaQwrqfpSePkMT": "👹 +$103K",
    "HtucFepgUkMpHdrYsxMqjBNN6qVBdjmFaLZneNXopuJm": "🥵 Qaunt",
    "J8fYZbmCnAL5WByigxqoum1disKUrZbsAmupfkXMvrmw": "🏁 Wallet 203",
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
    "8eioZubsRjFkNEFcSHKDbWa8MkpmXMBvQcfarGsLviuE": "🍔 +90k",
    "BKT1dCmc72rpsMExWooyTNqs2Qh6MeYMYX68B7JjqdLN": "🪕 +78K",
    "BXAWg4JbaeyvAHpiyYQ3Xr3bUh6FsyDHwwSkB5dmyGF": "👺 ?",
    "2rWMzY58HAvhR4KByBBtuYohptK1xikRSRHPKfJphcQS": "🔦 track",
    "AGqjivJr1dSv73TVUvdtqAwogzmThzvYMVXjGWg2FYLm": "🏐 +$47K?",
    "F5jWYuiDLTiaLYa54D88YbpXgEsA6NKHzWy4SN4bMYjt": "🎹 NEW-545",
    "525LueqAyZJueCoiisfWy6nyh4MTvmF4X9jSqi6efXJT": "🍙 joji",
    "HYMmhz7YBGHLtcvULf2UJSb7Du8p6XFHC3wB3CVeoHm7": "🎋 +$93.5K",
    "2BSwyjCDsxVEXf7DNaqt8ySoaodfuufEpFTxifFHSrsV": "✂ ?2",
    "4M5wSoZyfRsLMHJ2UGuUHYHQ2a5Q72Q7FnGKAS54fCC1": "🕸 +50K",
    "RFSqPtn1JfavGiUD4HJsZyYXvZsycxf31hnYfbyG6iB": "✌ 2",
    "Cvmo9SmWvBabC6ssW5uwThNKWipYJ6UUycBf4dibdQ97": "👠 +$275K",
    "9EyPAMyQvXaUWFxd2uQHvG8vpkKs33YdXvDvwmRXrUiH": "🍬 +$102K",
    "7VBTpiiEjkwRbRGHJFUz6o5fWuhPFtAmy8JGhNqwHNnn": "🐲 Brox",
    "4jSmEmBkuBi1JxZHM1khkf57xPR2oW1EnkRxqehq1cSK": "🎸 Wallet 199",
    "FTkq9ze7Q5X6gVoZ2X6RxbFqoKuzuQbzvWFTsw544cDL": "🔧 +$54.7K",
    "Gmh3Wt423pU6GsS3FQyZjknifnAFW7g3J8HhbF2TrbZL": "🔪 Scalper2",
    "BTf4A2exGK9BCVDNzy65b9dUzXgMqB4weVkvTMFQsadd": "🐯 LEV",
    "Av3xWHJ5EsoLZag6pr7LKbrGgLRTaykXomDD5kBhL9YQ": "🏋 YOLO",
    "86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD": "🐕 publix",
    "86ssNTYmFVux4NABe22hjjicVsgLzaNfgQzLa1ScicPg": "✏ ++",
    "719sfKUjiMThumTt2u39VMGn612BZyCcwbM5Pe8SqFYz": "💻 FASHR",
    "3tc4BVAdzjr1JpeZu6NAjLHyp4kK3iic7TexMBYGJ4Xk": "🤡 gnf",
    "FvPEk72M6Lp78idz5fbgXZijvaRPgXJGkkJs21hBSWJD": "🧩 +50k",
    "AJ6MGExeK7FXmeKkKPmALjcdXVStXYokYNv9uVfDRtvo": "🦝 TIM",
    "EQKeA12n4hvs4GhHmdcTMUSkUDF3aurw6zjLXogsw7Sk": "🥥 +$91k",
    "9WyrxBxc6kf8fq1UfmTTtCC7UfBmEGhQkDuWjxoHfvb7": "🚜 346H",
    "Fh3kfdQGDwzpiiME3X3h6dsbayd3ufrfP3GrdmJ7LKJT": "🗜 +$41.2k",
    "6TbDFs2dkHETrRWVbheiC11bwg7EWLDgszsCADF1ML1b": "🐙 +$42k",
    "As7HjL7dzzvbRbaD3WCun47robib2kmAKRXMvjHkSMB5": "🍡 Scalper3",
    "HPg7D2urG2B4z2BwKkS8z5HEwRRDKbtmYnAE31oCWzjL": "🎪 +$46k",
    "9rYDSfpA5pLWZakvBSKW5xJAktwDvAQ6m5VDeY4reF4M": "🐣 +95k",
    "5fprK2GKVWvrLTH6QzfmsNnFx4XJSFHc9Da7DDMshqbK": "⛺ NEW-96",
    "Fk9gqZHciE4HKonoeVuF5AHgU8WJZPuuvm1HehSxmRJQ": "🍐 452H",
    "G3g1CKqKWSVEVURZDNMazDBv7YAhMNTjhJBVRTiKZygk": "🗼 insider",
    "2kv8X2a9bxnBM8NKLc6BBTX2z13GFNRL4oRotMUJRva9": "👻 Gh0stee",
    "FxSuDZSxfouRxKH8LqGUHaecvQTrUNUvh9hk3HRAXiGa": "💋 +70k",
    "BJXjRq566xt66pcxCmCMLPSuNxyUpPNBdJGP56S7fMda": "📆 NEW-560",
    "FRa5xvWrvgYBHEukozdhJPCJRuJZcTn2WKj2u6L75Rmj": "📨 206H",
    "BLhQ4fWgkNAJ4MWXSdXaTnxwZxwHh7QTnMQb6i3Z2QYy": "🌙 90H",
    "63oQYEauMBFyaGQ69CNkwXFzCvdkFxdPaxGKYx72Tedb": "🎉 120H",
    "2HpvvY7TcbSdr8uNrDBUyEvbD9mcjg4ssmWQFcQcwJap": "🦊 NEW-199",
    "DsqRyTUh1R37asYcVf1KdX4CNnz5DKEFmnXvgT4NfTPE": "🍗 Classic",
    "EPFDmjJKBX1JrHHpzWRffZQv6jeZuo6o3g6FoeKJG5Ha": "🐆 447H",
    "5owZXjEe27wZTRevqRUETwia3EctJiaYtKhpqmPzWHuj": "🎨 +$90.8k",
    "52YXFG9ksGps7P9ZSDLK79f9Hpa5ihR24w6dkikW5aEB": "👗 49%-30k",
    "8Hw9X9UwBso7Sp2CFnEEeUGW8pGDj9wghc78ccWFZWpU": "💨 +50k",
    "7SDs3PjT2mswKQ7Zo4FTucn9gJdtuW4jaacPA65BseHS": "😀 Insentos",
    "CW6XezzEftYw4aALKo96x6oudqBZ3sfVXrfF23hAezdX": "🦴 295H",
    "EJvokC7vFEubsdEmJX3do1FgfwdUSDYZKGVa5MMs2isA": "🍄 +40k",
    "4gLZztSiwUnQtbqzc6sJrTjfgA5RCweHgokiLgEWPn3u": "🦍 +$168K",
    "8rvAsDKeAcEjEkiZMug9k8v1y8mW6gQQiMobd89Uy7qR": "🎰 casino",
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm": "🦩 gake",
    "AEtL29wgARtujVynpgoDtUMLvM7NmZ6WALcjD2NjU8Dk": "🛢 +$166K КИТ",
    "242p259rfsb9J3X3mhnWw35UM2hfMDg14G47CQ66s9ZW": "💨 NEW-3",
    "2HWT2KLLdN2wxYTqdSuko5SBzg2SEJASgV4GE2tD7TML": "🏗 164H",
    "76ZUBj1JLz7arTVHSRJok5oSTEqDuVBgySFMVHtzxzZc": "❓ +$87.1K",
    "3BLjRcxWGtR7WRshJ3hL25U3RjWr5Ud98wMcczQqk4Ei": "🙊 Sebastian",
    "77n6X7LtGy5AZprsvjZu1eaekJpxqLeVRZLPJZdBYyg9": "⭐ 242H",
    "BCagckXeMChUKrHEd6fKFA1uiWDtcmCXMsqaheLiUPJd": "🦹 &dv",
    "6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC": "⛷ 184H",
    "8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs": "🍶 big bags",
    "AeLaMjzxErZt4drbWVWvcxpVyo8p94xu5vrg41eZPFe3": "😡 simle",
    "GrXjXop95XkVPYJafDJNCLFzK9K8LkpopxYcgUUn2H87": "🦁 NEW-189",
    "mW4PZB45isHmnjGkLpJvjKBzVS5NXzTJ8UDyug4gTsM": "🐺 igndex",
    "XXXXXahGswEH6i3Czn19XbGxQrobJoY1TYJegPxp3ex": "🦜 +$73.1k",
    "JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN": "🍃 WEST",
    "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": "🍍 254H",
    "53BnNc49Ajgstciq3CRoyxuBpkkW1r8pgPyvr7JGYnsh": "👾 Monki",
    "4nvNc7dDEqKKLM4Sr9Kgk3t1of6f8G66kT64VoC95LYh": "🐌 a",
    "7aMgK5L4qEQ8Nyv6ZzhZi2B82NSSRnwb2NGJnNagA46D": "🍿 70%+66k",
    "J6TDXvarvpBdPXTaTU8eJbtso1PUCYKGkVtMKUUY8iEa": "🧂 +$115k",
    "4SbDMrX8Zfj7qZtRKTBSQEavPkc7BP1kiJfT2f3dn8RL": "🦈 АКУЛА",
    "8MaVa9kdt3NW4Q5HyNAm1X5LbR8PQRVDc1W8NMVK88D5": "🏖 Daumen",
    "CLegS2MSiCsBksVazCg4Y7Gz3NqeBK21QyvzK4Q7S168": "🐝 NEW-13",
    "CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o": "👽 kentes",
    "5h7yzwmrGoG2BmxNCqNR2EnSv1LWCFo7n6SKSh5ZWkfE": "🖌 307H",
    "4CqecFud362LKgALvChyhj6276he3Sy8yKim1uvFNV1m": "🥴 182H",
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk": "🦥 GIGO",
    "2C5m99kgdKkiwZCm5qLjpLXrrKAuz1FtM3GoenWkSD8w": "👠 478H",
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
    "EjaMRoxyHFSLdMtRtXLtinT96mTHhEdp9jubVubwWtxr": "🦋 OLD",
    "A2B76kth3LZB7GK6dSzRcZBYNWsn2K6fCWyKVXBFqKx4": "🥩 252H",
    "HYWo71Wk9PNDe5sBaRKazPnVyGnQDiwgXCFKvgAQ1ENp": "🐑 268H",
    "7mGZh58meFf8xsES37bc2hdffEmh8aTDcB2i725Zivyg": "🎷",
    "DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC": "🛷 362H",
    "BQVz7fQ1WsQmSTMY3umdPEPPTm1sdcBcX9sP7o6kPRmB": "🦀 +41.9K",
}

# ================= HELPERS =================
def short(addr): return f"{addr[:4]}...{addr[-4:]}"

def emoji(w):
    return WALLET_EMOJI.get(w, f"🔹 {short(w)}")

def hold_percent(wallet, mint):
    with lock:
        b = ledger[(wallet, mint)]["buy"]
        s = ledger[(wallet, mint)]["sell"]
    if b <= 0: return 0
    return max(0, int(((b - s) / b) * 100))

def status_icon(pct):
    if pct >= 100: return "🔷"
    if pct <= 0:   return "🔺"
    return "🔶"

def format_mc(mc):
    if not mc: return "N/A"
    return f"${mc/1_000_000:.2f}M" if mc >= 1_000_000 else f"${mc/1000:.1f}K"

def tx_age_str(ts):
    diff = int(time.time() - ts)
    if diff < 60:   return f"{diff}s tx"
    if diff < 3600: return f"{diff//60}m tx"
    return f"{diff//3600}h tx"

def seen_str(first_ts):
    diff = int(time.time() - first_ts)
    if diff < 60:   return "<1m"
    if diff < 3600: return f"{diff//60}m"
    return f"{diff//3600}h"

# ================= JUPITER FALLBACK =================
def get_jupiter_data(mint):
    """
    Резервне джерело даних — Jupiter API.
    Повертає (symbol, mc) або (None, 0) якщо не знайдено.
    Jupiter знає про всі токени на Solana включно з Orca/Meteora/старими токенами.
    """
    try:
        # Jupiter token info
        r = requests.get(
            f"https://tokens.jup.ag/token/{mint}",
            timeout=5
        ).json()
        symbol = r.get("symbol")

        # Jupiter price API для MC
        price_r = requests.get(
            f"https://price.jup.ag/v6/price?ids={mint}",
            timeout=5
        ).json()
        price_data = price_r.get("data", {}).get(mint, {})
        price = price_data.get("price", 0)

        # MC = price * supply (якщо є)
        supply = r.get("extensions", {}).get("coingeckoId") or 0
        mc = 0
        if price and r.get("tags"):
            # Беремо marketCap напряму якщо є
            mc = price_data.get("marketCap", 0) or 0

        return symbol, mc
    except Exception as e:
        logging.warning(f"Jupiter fallback error {mint[:8]}: {e}")
        return None, 0

# ================= SYMBOL CACHE =================
def get_symbol(mint):
    now = time.time()
    if mint in symbol_cache:
        sym, ts = symbol_cache[mint]
        if now - ts < SYMBOL_TTL:
            return sym

    # Спроба 1: dexscreener
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
            timeout=5
        ).json()
        if r.get("pairs"):
            sym = r["pairs"][0]["baseToken"]["symbol"]
            symbol_cache[mint] = (sym, now)
            return sym
    except Exception as e:
        logging.warning(f"get_symbol dexscreener error {mint[:8]}: {e}")

    # Спроба 2: Jupiter fallback
    try:
        r = requests.get(f"https://tokens.jup.ag/token/{mint}", timeout=5).json()
        sym = r.get("symbol")
        if sym:
            symbol_cache[mint] = (sym, now)
            return sym
    except Exception as e:
        logging.warning(f"get_symbol jupiter error {mint[:8]}: {e}")

    # Не кешуємо якщо не отримали — щоб наступний запит повторив
    return mint[:6]

# ================= MARKET CACHE =================
def get_market(mint):
    """
    ✅ Sticky MC cache + Jupiter fallback:
    Структура: (mc, pair, fetch_ts, valid_mc, valid_pair)
    - valid_mc/valid_pair — останні валідні дані, НІКОЛИ не замінюються нулем
    - Якщо dexscreener повертає 0 — пробуємо Jupiter
    - Якщо обидва повернули 0 — тримаємо попередні валідні дані
    """
    now = time.time()

    if mint in market_cache:
        mc, pair, fetch_ts, valid_mc, valid_pair = market_cache[mint]
        if now - fetch_ts < MARKET_TTL:
            return valid_mc, valid_pair

    # Отримуємо попередні валідні дані
    prev_valid_mc   = 0
    prev_valid_pair = None
    if mint in market_cache:
        _, _, _, prev_valid_mc, prev_valid_pair = market_cache[mint]

    # Спроба 1: dexscreener
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
            timeout=5
        ).json()

        if r.get("pairs"):
            # Спочатку шукаємо solana пару, якщо немає — беремо будь-яку
            sol_pairs = [x for x in r["pairs"] if x.get("chainId") == "solana"]
            p = sol_pairs[0] if sol_pairs else r["pairs"][0]
            mc   = p.get("fdv", 0) or 0
            pair = p.get("pairAddress")

            # ✅ Якщо fdv = 0 — пробуємо marketCap або priceUsd * supply
            if mc == 0:
                mc = p.get("marketCap", 0) or 0
            if mc == 0 and p.get("priceUsd") and p.get("liquidity", {}).get("usd"):
                # Груба оцінка через ліквідність якщо немає fdv
                pass

            if mc > 0:
                market_cache[mint] = (mc, pair, now, mc, pair)
                return mc, pair
            else:
                # fdv відсутній — спробуємо Jupiter нижче
                pass
        # Немає пар або mc = 0 — падаємо в Jupiter fallback
    except Exception as e:
        logging.warning(f"get_market dexscreener error {mint[:8]}: {e}")

    # Спроба 2: Jupiter Price API
    try:
        price_r = requests.get(
            f"https://price.jup.ag/v6/price?ids={mint}",
            timeout=5
        ).json()
        price_data = price_r.get("data", {}).get(mint, {})
        mc_jup = price_data.get("marketCap", 0) or 0

        if mc_jup > 0:
            logging.info(f"Jupiter MC found: {format_mc(mc_jup)} for {mint[:8]}")
            # pair беремо з попередніх валідних або None
            market_cache[mint] = (mc_jup, prev_valid_pair, now, mc_jup, prev_valid_pair)
            return mc_jup, prev_valid_pair
    except Exception as e:
        logging.warning(f"get_market jupiter error {mint[:8]}: {e}")

    # Обидва не дали результат — НЕ затираємо валідні дані
    market_cache[mint] = (0, prev_valid_pair, now, prev_valid_mc, prev_valid_pair)
    return prev_valid_mc, prev_valid_pair

def get_market_with_retry(mint, retries=3, delay=3):
    """3 спроби. Завжди повертає найкращі доступні дані."""
    best_mc, best_pair = 0, None
    for attempt in range(retries):
        mc, pair = get_market(mint)
        if mc > 0:
            return mc, pair
        if mc == 0 and best_mc == 0:
            best_mc, best_pair = mc, pair
        if attempt < retries - 1:
            logging.info(f"Retry MC {attempt+1}/{retries} for {mint[:8]}")
            time.sleep(delay)
    return best_mc, best_pair

def is_migrated(mc):
    """
    mc > MIN_MC_USD   → мігрував ✅
    mc == 0           → невідомо, відправляємо з ⚠️
    0 < mc < MIN_MC   → pump.fun, ігноруємо ❌
    """
    if mc == 0:
        return True
    return mc >= MIN_MC_USD

def build_axiom(mint, pair):
    return f"https://axiom.trade/meme/{pair if pair else mint}?chain=sol"

# ================= TELEGRAM =================
def send(text, url=None):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "AXIOM", "url": url}]]}
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload, timeout=8
        )
    except Exception as e:
        logging.error(f"TG error: {e}")

# ================= BUILD MULTI TEXT =================
def build_multi_text(mint, cl, mcap, sym_name):
    w_count   = len(cl["wallets"])
    total_sol = cl["total"]
    seen      = seen_str(cl["first_ts"])
    mc_str    = format_mc(mcap)
    mc_warn   = " ⚠️" if mcap == 0 else ""

    txt = (
        f"!! 🟢 <b>MULTI BUY {sym_name}</b>\n\n"
        f"{w_count} wallets bought <b>{sym_name}</b> in the last 6 hours!\n"
        f"Total: {total_sol:.2f} SOL\n\n"
    )
    for w, info in cl["wallets"].items():
        amt       = info["amt"]
        age       = tx_age_str(info["ts"])
        total_buy = ledger[(w, mint)]["buy"]
        hp        = hold_percent(w, mint)
        icon      = status_icon(hp)
        txt += (
            f"{icon} {emoji(w)} ({age})\n"
            f"|- <b>{amt:.2f} SOL</b> | MC {mc_str}{mc_warn}\n"
            f"|_ Total buy: {total_buy:.2f} SOL | 👊 {hp}%\n\n"
        )
    txt += f"🔗 #{sym_name} | MC: {mc_str}{mc_warn} | Seen: {seen}\n"
    txt += f"<code>{mint}</code>"
    return txt

# ================= CLEANER =================
def cleanup_loop():
    while True:
        time.sleep(1800)
        now = time.time()
        with lock:
            for sig in list(processed_signatures):
                if now - processed_signatures[sig] > SIGNATURE_TTL:
                    del processed_signatures[sig]
            for k in list(wallet_agg):
                if now - wallet_agg[k]["first_ts"] > 600:
                    del wallet_agg[k]
            for k in list(clusters):
                if now - clusters[k]["first_ts"] > CLUSTER_LIFETIME + 3600:
                    del clusters[k]
                    sent_multi.pop(k, None)
            for k in list(sent_ordinary):
                if now - sent_ordinary[k] > CLUSTER_LIFETIME:
                    del sent_ordinary[k]
            for k in list(ledger):
                if now - ledger[k].get("last_ts", 0) > 86400:
                    del ledger[k]
            for m in list(symbol_cache):
                if now - symbol_cache[m][1] > SYMBOL_TTL * 2:
                    del symbol_cache[m]
            for m in list(market_cache):
                if now - market_cache[m][2] > 7200:
                    del market_cache[m]
        logging.info(
            f"[Cleanup] sigs={len(processed_signatures)} "
            f"clusters={len(clusters)} ledger={len(ledger)}"
        )

threading.Thread(target=cleanup_loop, daemon=True).start()

# ================= ACTIVE MULTI =================
def is_active_multi(mint):
    if mint not in sent_multi:
        return False
    if mint in clusters:
        if time.time() - clusters[mint]["first_ts"] < CLUSTER_LIFETIME:
            return True
    return False

# ================= ORDINARY ALERT =================
def delayed_ordinary_send(wallet, mint, key):
    now = time.time()
    with lock:
        if is_active_multi(mint):
            logging.info(f"Ordinary suppressed (multi): {mint[:8]}")
            wallet_agg.pop(key, None)
            return
        if key not in wallet_agg:
            return
        final_amt = wallet_agg[key]["amount"]
        del wallet_agg[key]
        sent_ordinary[key] = now

    symbol = get_symbol(mint)
    if symbol.upper() in STABLE_SYMBOLS:
        return

    mc, pair = get_market_with_retry(mint)

    if not is_migrated(mc):
        logging.info(f"Ordinary skipped — pump.fun: MC {format_mc(mc)} for {symbol}")
        return

    ax        = build_axiom(mint, pair)
    hp        = hold_percent(wallet, mint)
    mc_str    = format_mc(mc)
    mc_warn   = " ⚠️" if mc == 0 else ""
    total_buy = ledger[(wallet, mint)]["buy"]

    logging.info(f"SEND ordinary | {emoji(wallet)} | {symbol} | {final_amt:.2f} SOL | MC {mc_str}")

    txt = (
        f"🟢 <b>BUY {symbol}</b>\n\n"
        f"{status_icon(hp)} {emoji(wallet)}\n"
        f"|- <b>{final_amt:.2f} SOL</b> | MC {mc_str}{mc_warn}\n"
        f"|_ Total buy: {total_buy:.2f} SOL | 👊 {hp}%\n\n"
        f"<code>{mint}</code>"
    )
    send(txt, ax)

# ================= MULTI ALERT =================
def send_multi_alert(mint, sym_name):
    """
    ✅ Логіка:
    bandit  → 1й
    publix  → 2й
    27H     → 3й → таймер 5с → відправляємо (3 > 0)  sent_count=3
    gnf     → 4й → таймер 5с → відправляємо (4 > 3)  sent_count=4
    """
    with lock:
        if mint not in clusters:
            return
        cl      = clusters[mint]
        w_count = len(cl["wallets"])
        last    = sent_multi.get(mint, {"count": 0, "ts": 0})

        # Відправляємо тільки якщо є нові гаманці з моменту останньої відправки
        if w_count < MULTI_MIN_WALLETS or w_count <= last["count"]:
            logging.info(f"Multi skip — w={w_count} last={last['count']} for {mint[:8]}")
            return

        sent_multi[mint] = {"count": w_count, "ts": time.time()}

        # Скасовуємо pending ordinary
        for k in list(wallet_agg):
            if k[1] == mint:
                del wallet_agg[k]

        snapshot = {
            "wallets":  {w: dict(info) for w, info in cl["wallets"].items()},
            "total":    cl["total"],
            "first_ts": cl["first_ts"],
        }

    mc, pr = get_market_with_retry(mint)

    if not is_migrated(mc):
        logging.info(f"Multi skipped — pump.fun: MC {format_mc(mc)} for {sym_name}")
        return

    # Якщо символ виглядає як обрізаний mint — пробуємо отримати свіжий
    if len(sym_name) <= 6 and sym_name == mint[:len(sym_name)]:
        fresh = get_symbol(mint)
        if fresh != mint[:6]:
            sym_name = fresh

    ax  = build_axiom(mint, pr)
    txt = build_multi_text(mint, snapshot, mc, sym_name)

    logging.info(
        f"SEND multi | {sym_name} | {len(snapshot['wallets'])} wallets | "
        f"{snapshot['total']:.2f} SOL | MC {format_mc(mc)}"
    )
    send(txt, ax)

# ================= WEBHOOK =================
@app.route("/", methods=["POST"])
def webhook():
    txs = request.json
    if not isinstance(txs, list):
        return jsonify(ok=True)

    now = time.time()

    for tx in txs:
        sig = tx.get("signature")
        if not sig:
            continue
        with lock:
            if sig in processed_signatures:
                continue
            processed_signatures[sig] = now

        wallet = tx.get("feePayer")
        if not wallet:
            continue

        net_sol = 0
        for acc in tx.get("accountData", []):
            if acc.get("account") == wallet:
                net_sol = acc.get("nativeBalanceChange", 0) / 1e9

        sol_abs = abs(net_sol)
        if sol_abs <= 0.005:
            continue

        bought_mint = None
        seen_mints  = set()

        for t in tx.get("tokenTransfers", []):
            mint = t.get("mint")
            if mint == SOL_MINT or mint in seen_mints:
                continue
            if t.get("toUserAccount") == wallet:
                with lock:
                    ledger[(wallet, mint)]["buy"]    += sol_abs
                    ledger[(wallet, mint)]["last_ts"] = now
                bought_mint = mint
                seen_mints.add(mint)
            elif t.get("fromUserAccount") == wallet:
                with lock:
                    ledger[(wallet, mint)]["sell"]   += sol_abs
                    ledger[(wallet, mint)]["last_ts"] = now
                seen_mints.add(mint)

        if not bought_mint:
            continue
        if bought_mint in STABLE_MINTS:
            continue

        symbol = get_symbol(bought_mint)
        if symbol.upper() in STABLE_SYMBOLS:
            continue

        logging.info(f"BUY | {emoji(wallet)} | {symbol} | {sol_abs:.2f} SOL")

        key = (wallet, bought_mint)

        # --- Ordinary ---
        with lock:
            is_recent = key in sent_ordinary and now - sent_ordinary[key] < CLUSTER_LIFETIME
            if not is_recent and not is_active_multi(bought_mint):
                if key not in wallet_agg:
                    wallet_agg[key] = {"amount": sol_abs, "first_ts": now, "timer_started": False}
                else:
                    wallet_agg[key]["amount"] += sol_abs
                if wallet_agg[key]["amount"] >= MIN_BUY_SOL and not wallet_agg[key]["timer_started"]:
                    wallet_agg[key]["timer_started"] = True
                    # ✅ 20 секунд — більше ніж multi (15с), щоб multi завжди спрацював першим
                    threading.Timer(20.0, delayed_ordinary_send,
                                    args=[wallet, bought_mint, key]).start()

        # --- Multi ---
        if sol_abs >= MULTI_MIN_SOL:
            with lock:
                if (bought_mint not in clusters
                        or now - clusters[bought_mint]["first_ts"] > CLUSTER_LIFETIME):
                    clusters[bought_mint] = {
                        "wallets":  {},
                        "total":    0.0,
                        "first_ts": now,
                        "sym":      symbol,
                    }

                cl = clusters[bought_mint]

                if wallet in cl["wallets"]:
                    cl["wallets"][wallet]["amt"] += sol_abs
                    cl["wallets"][wallet]["ts"]   = now
                    cl["total"] += sol_abs
                else:
                    cl["wallets"][wallet] = {"amt": sol_abs, "ts": now}
                    cl["total"] += sol_abs

                # ✅ Фіксуємо символ — беремо перший валідний (не обрізаний mint)
                # Якщо поточний sym виглядає як обрізаний mint — оновлюємо
                current_sym = cl.get("sym", "")
                is_stub = (len(current_sym) <= 6 and current_sym == bought_mint[:len(current_sym)])
                is_valid_sym = (len(symbol) > 1 and symbol != bought_mint[:6])
                if is_stub and is_valid_sym:
                    cl["sym"] = symbol

                w_count     = len(cl["wallets"])
                snap_symbol = cl.get("sym", symbol)
                last_count  = sent_multi.get(bought_mint, {"count": 0})["count"]

                # ✅ Таймер запускається для КОЖНОГО нового гаманця >= порогу
                # bandit=1, publix=2, 27H=3→таймер→відправить, gnf=4→таймер→відправить
                should_fire = w_count >= MULTI_MIN_WALLETS and w_count > last_count

            if should_fire:
                # ✅ 15 секунд — достатньо щоб зібрати всі одночасні покупки
                threading.Timer(
                    15.0, send_multi_alert,
                    args=[bought_mint, snap_symbol]
                ).start()

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
