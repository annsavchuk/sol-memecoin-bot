import os
import time
import requests
import threading
import logging
from flask import Flask, request, jsonify
from collections import defaultdict

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s [%(levelname)s] %(message)s”
)
app = Flask(**name**)

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv(“TELEGRAM_TOKEN”)
CHAT_ID        = os.getenv(“CHAT_ID”)

MIN_BUY_SOL       = 5
MULTI_MIN_SOL     = 5
MULTI_MIN_WALLETS = 3
CLUSTER_LIFETIME  = 6 * 3600
SIGNATURE_TTL     = 600

STABLE_SYMBOLS = {“SOL”, “WSOL”, “USDC”, “USDT”, “DAI”, “USD”, “SOLANA”}

STABLE_MINTS = {
“EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v”,
“Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB”,
“7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs”,
“So11111111111111111111111111111111111111112”,
“mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So”,
“7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj”,
“bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1”,
}

SOL_MINT = “So11111111111111111111111111111111111111112”

# ================= STATE =================

wallet_agg           = {}

# clusters[mint] = {

# “wallets”: { addr: {“amt”: float, “ts”: float} },

# “total”: float,

# “first_ts”: float,

# “sym”: str

# }

clusters             = {}
ledger               = defaultdict(lambda: {“buy”: 0.0, “sell”: 0.0, “last_ts”: 0.0})
sent_ordinary        = {}

# sent_multi[mint] = {“count”: int, “ts”: float}

sent_multi           = {}
processed_signatures = {}

lock = threading.Lock()

# ================= CACHES =================

symbol_cache = {}
market_cache = {}
SYMBOL_TTL   = 3600
MARKET_TTL   = 30

# ================= WALLET EMOJI =================

WALLET_EMOJI = {
“BiNp5o3D1NDX4U67wbdvq9nTZUmDoiMRMbNn4dJB2rP9”: “🐹 365Н”,
“C3nLTNMK6Ao1s3J1CQhv8GbT3NoMmifWoi9PGEcYd9hP”: “👮 +$57.7K?”,
“8fSnLTnRViK83dDesivTsPx2wiRhwti9xoafeMGjEyLJ”: “🎗️ 27H”,
“BC8yiFFQWFEKrEEj75zYsuK3ZDCfv6QEeMRif9oZZ9TW”: “🥟 ?”,
“HEW8TmjdtJmAeMWZYG2pZd97FwZybtvJMkFjJmqMz64E”: “⛸️ ?”,
“BHREKFkPQgAtDs8Vb1UfLkUpjG6ScidTjHaCWFuG2AtX”: “🎺 &”,
“9jyqFiLnruggwNn4EQwBNFXwpbLM9hrA4hV59ytyAVVz”: “😁 NACH”,
“xXpRSpAe1ajq4tJP78tS3X1AqNwJVQ4Vvb1Swg4hHQh”: “🪀 aloh”,
“GybhvUZzTq4qYBc292dz4HE4oQPZJGC9xGJdEH9uYeHK”: “⛺ КИТ”,
“9yYya3F5EJoLnBNKW6z4bZvyQytMXzDcpU5D6yYr4jqL”: “🥕 loopierr”,
“A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL”: “🛠️ Wallet 88”,
“929fdCX5PbGr7rxrUb7GEyVbxka9WXszGkzHrnnCZ58m”: “🔱 +”,
“ApRnQN2HkbCn7W2WWiT2FEKvuKJp9LugRyAE1a9Hdz1”: “🌐 S”,
“3ZsXXbXheMS2D6D6RRuJhERwh82aTgLy2JwFv6PRc4bM”: “🍀 ?”,
“BtMBMPkoNbnLF9Xn552guQq528KKXcsNBNNBre3oaQtr”: “🌠 NEW-210”,
“3h65MmPZksoKKyEpEjnWU2Yk2iYT5oZDNitGy5cTaxoE”: “🚢 Wallet 13”,
“DKgvpfttzmJqZXdavDwTxwSVkajibjzJnN2FA99dyciK”: “🦆 167H”,
“FSvK6sxyLje1A8V7pbXWyroqyFmN41j5oseDCBHjTXL4”: “🧢 NEW-305”,
“8deJ9xeUvXSJwicYptA9mHsU2rN2pDx37KWzkDkEXhU6”: “👷 Cooker”,
“G1pRtSyKuWSjTqRDcazzKBDzqEF96i1xSURpiXj3yFcc”: “🌺 87Н”,
“286CHN57Km41GsAnDv866WKd6YB6HPSjFgF4rGDJTRLf”: “🐼 NEW-50”,
“6T8Yr9DUUS2R8GHevaeaZcoxA1Jku51ZBkmcM7NaZiNE”: “🌭 306Н”,
“4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD”: “🐘 23Н”,
“BH84Uo2YAnyWRUWeWyfFzttRmE51V682xUaD6NrLHM88”: “🔑 100Н”,
“GwyG5FQRNtY1faXYWdTLbcDNZTyW5d2Z63o1UiMUDQDT”: “🥨?”,
“34ZEH778zL8ctkLwxxERLX5ZnUu6MuFyX9CWrs8kucMw”: “⚓ 111к”,
“CueDkwDYr8ZXRwMseprUpCqsz1Zj1VgLnZNRFyQHkfwZ”: “7⃣ 284Н”,
“3in1nAQoJdnTZsYdmgVfJFLrRR1EoE3HVjyVnZVTMULV”: “🦃 279К”,
“HuP4RYp6ZRmhjikmbaHqzNwA71JoQ7oqQMHEZHUWQ4Rb”: “⛱ 214”,
“M5Q1hFKopMr2DyNabEkrgoh6tGaF6z6NVQZ5SGUPss8”: “🪓 Wallet 159”,
“DMqibTACAF4piJjA92Kuim7pxzuNGFizmuZ5KTtttnx8”: “🥪”,
“CdFHmaj37EtjgRqvyt6vZqoA9tuMSvKLSmbgpuV6ejaP”: “💊 442H”,
“F9meywQee74tqAKQvDb4Q9bon7y2XLNwUyFYUNEQUto9”: “🏆”,
“2RssnB7hcrnBEx55hXMKT1E7gN27g9ecQFbbCc5Zjajq”: “🥴 mostache”,
“DiddyP7tSoS5e26zzy43QVfgTQ3dJ8ZyLibC3uPAAwQk”: “🧙 DiddyP&&&&”,
“FhLmFRG4iUAN48jXkuEc2fAz9E9ZUbZuW2my7g8TFvsC”: “🛒 Wallet 110”,
“ERgtHKpakjFBtcgrh4abzpqFCQKsMdM7QXdE1sfafrWU”: “🏅 361Н”,
“Gf9XgdmvNHt8fUTFsWAccNbKeyDXsgJyZN8iFJKg5Pbd”: “🦓 10H”,
“BZi5L1mCmVjXdUmeCRQWfKvuWqXakmRYQPFpmS559hD1”: “⌛ 118Н”,
“99i9uVA7Q56bY22ajKKUfTZTgTeP5yCtVGsrG9J4pDYQ”: “🥺 Zrool”,
“GjBhR6AY2h8d9rg3xrnQpSYRgK57eAnJs8agYFCkA1qM”: “🍯 +$93.6K”,
“87MZqjjJgpuFvaU8GyQJKbZGnCFFhX82qAjBGLRXPfcn”: “🥁 Nyhrox”,
“pndujwi7BeaRRenYHSShyNQXAdBNEzKDR5jgzbheJFT”: “🍺 ?”,
“Gq1RQQcvbZu9Ud2wVRy6Krh9RsS1ZYbLBsBuMuvCgyRU”: “🌽”,
“9ZzjXiwkGRDBwVHJitfx8AmnN2YUbnqW6M1tH38juEeJ”: “🎉 NEW-321”,
“9HCTuTPEiQvkUtLmTZvK6uch4E3pDynwJTbNw6jLhp9z”: “🎡 Wallet 236”,
“DgJxxRStmjsuK1EbPBuVuH7cd68XHKUNV33aeoUfS8ai”: “🔍 364Н”,
“HRFekhACsTUj9tRNHR8VfgBSYZp4BodaQwrqfpSePkMT”: “👹 +$103K”,
“HtucFepgUkMpHdrYsxMqjBNN6qVBdjmFaLZneNXopuJm”: “🥵 Qaunt”,
“J8fYZbmCnAL5WByigxqoum1disKUrZbsAmupfkXMvrmw”: “🏁 Wallet 203”,
“CDNt6H6J7ZBWVjyKJmFRjcJAoHa6XKrn2mTLK3DZwnqL”: “🥐 +$86.4K”,
“4Degk564qYYcK4hDZikpNcuS4jNgcGH8PGcJuhgJdPoY”: “🦠 new-3”,
“7ABz8qEFZTHPkovMDsmQkm64DZWN5wRtU7LEtD2ShkQ6”: “🔴 red”,
“BCnqsPEtA1TkgednYEebRpkmwFRJDCjMQcKZMMtEdArc”: “🎄 kreo”,
“DEdEW3SMPU2dCfXEcgj2YppmX9H3bnMDJaU4ctn2BQDQ”: “🦕 new-72”,
“4Be9CvxqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7t”: “🍀 MITH”,
“7wiEWKeG7sFUNh1TgujwCa9cmJtSSE4mNLDde7knjoeE”: “🛰 +$32.2K”,
“BXNiM7pqt9Ld3b2Hc8iT3mA5bSwoe9CRrtkSUs15SLWN”: “🎧 ABSOL”,
“AUqmxUYP9pmU4JwMhQiDKc2TNUCzxE5SGoikqFuKCLQT”: “🎬 +$56.2K”,
“HwAzzsi2NMirgRDs1LeUTLsPENgfL7pBss5ynEpwV7aY”: “🐢 NEW-7”,
“3pkY4S76Jw1UDS8Qgz4wD3DxrTxz7QfyC8yTbXJoZcMT”: “🦘 Kai”,
“6EDaVsS6enYgJ81tmhEkiKFcb4HuzPUVFZeom6PHUqN3”: “🛵”,
“GJyhzLoZAxZHZGPvF3V1wsyGUnoGSQ55n6hN6nHv7W8B”: “🏀 LilmoonLambo”,
“7Eio5ydwGrqkcQMcSahAyYgergkSt2PKkzK2Pc8seMEr”: “🐈 +$60.8K?”,
“2iCmwtaM14u5XijJ6Wx6pbxSqvvPbvzUVXAhk1B4aEtr”: “🥊 251H”,
“GMfBfVi5CAVfVHn3FoGvxQY7aJeYZLwYLZDenZkBGR2p”: “🧸 NEW-6”,
“6sqSp6ejH4jxtreZBGB4LYeAwYK4SsKomBKPEf3trL2C”: “🛹 +35K”,
“3wZ6MfB1DRUvtozvcptvV1qAhQ5FKj3qpZR4Db45G6jk”: “🤑 ?”,
“4jgTN9YNrq4wCqRJ7tRne4u3S7prjGmvuASy2C36fN6y”: “✈ 328H”,
“CBaM2xaPdDdhaopd8dD93LJAvextJoPngdKFz8QFP7JD”: “📌 NEW-53”,
“6LChaYRYtEYjLEHhzo4HdEmgNwu2aia8CM8VhR9wn6n7”: “🤠 assasin.eth”,
“4u3Baa6znzQ6pjQRLii8KV9tRhtNuXCqwVcY3b6nNpaZ”: “🍆 +$303”,
“KzxoVgkSDR7xXYKykbLmSBKMdwzGTesZS7Mc2iXkK9u”: “📙 1”,
“8qX6LuKeDmR6FLg8HhmFxQHKhJbhx1zmRgoCk5RCmbk5”: “🐧 366H”,
“8PWPhnXh7P7bwoinAavyqsnU33H67x9wkRCxyAWibGD8”: “🐽 ? -60%”,
“8eioZubsRjFkNEFcSHKDbWa8MkpmXMBvQcfarGsLviuE”: “🍔 +90к”,
“BKT1dCmc72rpsMExWooyTNqs2Qh6MeYMYX68B7JjqdLN”: “🪕 +78К”,
“BXAWg4JbaeyvAHpiyYQ3Xr3bUh6FsyDHwwSkB5dmyGF”: “👺 ?”,
“2rWMzY58HAvhR4KByBBtuYohptK1xikRSRHPKfJphcQS”: “🔦 ame to track”,
“AGqjivJr1dSv73TVUvdtqAwogzmThzvYMVXjGWg2FYLm”: “🏐 +$47K?”,
“F5jWYuiDLTiaLYa54D88YbpXgEsA6NKHzWy4SN4bMYjt”: “🎹 NEW-545”,
“525LueqAyZJueCoiisfWy6nyh4MTvmF4X9jSqi6efXJT”: “🍙 joji”,
“HYMmhz7YBGHLtcvULf2UJSb7Du8p6XFHC3wB3CVeoHm7”: “🎋 +$93.5K”,
“2BSwyjCDsxVEXf7DNaqt8ySoaodfuufEpFTxifFHSrsV”: “✂ ?2”,
“4M5wSoZyfRsLMHJ2UGuUHYHQ2a5Q72Q7FnGKAS54fCC1”: “🕸 +50К”,
“RFSqPtn1JfavGiUD4HJsZyYXvZsycxf31hnYfbyG6iB”: “✌ 2”,
“Cvmo9SmWvBabC6ssW5uwThNKWipYJ6UUycBf4dibdQ97”: “👠 +$275K”,
“9EyPAMyQvXaUWFxd2uQHvG8vpkKs33YdXvDvwmRXrUiH”: “🍬 +$102K”,
“7VBTpiiEjkwRbRGHJFUz6o5fWuhPFtAmy8JGhNqwHNnn”: “🐲 Brox”,
“4jSmEmBkuBi1JxZHM1khkf57xPR2oW1EnkRxqehq1cSK”: “🎸 Wallet 199”,
“FTkq9ze7Q5X6gVoZ2X6RxbFqoKuzuQbzvWFTsw544cDL”: “🔧 +$54.7K”,
“Gmh3Wt423pU6GsS3FQyZjknifnAFW7g3J8HhbF2TrbZL”: “🔪 Скальпер2”,
“BTf4A2exGK9BCVDNzy65b9dUzXgMqB4weVkvTMFQsadd”: “🐯 LEV”,
“Av3xWHJ5EsoLZag6pr7LKbrGgLRTaykXomDD5kBhL9YQ”: “🏋 YOLO”,
“86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD”: “🐕 publix”,
“86ssNTYmFVux4NABe22hjjicVsgLzaNfgQzLa1ScicPg”: “✏ ++”,
“719sfKUjiMThumTt2u39VMGn612BZyCcwbM5Pe8SqFYz”: “💻 FASHR”,
“3tc4BVAdzjr1JpeZu6NAjLHyp4kK3iic7TexMBYGJ4Xk”: “🤡 gnf”,
“FvPEk72M6Lp78idz5fbgXZijvaRPgXJGkkJs21hBSWJD”: “🧩 +50k”,
“AJ6MGExeK7FXmeKkKPmALjcdXVStXYokYNv9uVfDRtvo”: “🦝 TIM”,
“EQKeA12n4hvs4GhHmdcTMUSkUDF3aurw6zjLXogsw7Sk”: “🥥 +$91к”,
“9WyrxBxc6kf8fq1UfmTTtCC7UfBmEGhQkDuWjxoHfvb7”: “🚜 346Н”,
“Fh3kfdQGDwzpiiME3X3h6dsbayd3ufrfP3GrdmJ7LKJT”: “🗜 +$41.2к”,
“6TbDFs2dkHETrRWVbheiC11bwg7EWLDgszsCADF1ML1b”: “🐙 +$42к”,
“As7HjL7dzzvbRbaD3WCun47robib2kmAKRXMvjHkSMB5”: “🍡 Скальпер3”,
“HPg7D2urG2B4z2BwKkS8z5HEwRRDKbtmYnAE31oCWzjL”: “🎪 +$46к”,
“9rYDSfpA5pLWZakvBSKW5xJAktwDvAQ6m5VDeY4reF4M”: “🐣 +95к”,
“5fprK2GKVWvrLTH6QzfmsNnFx4XJSFHc9Da7DDMshqbK”: “⛺ NEW-96”,
“Fk9gqZHciE4HKonoeVuF5AHgU8WJZPuuvm1HehSxmRJQ”: “🍐 452Н”,
“G3g1CKqKWSVEVURZDNMazDBv7YAhMNTjhJBVRTiKZygk”: “🗼 insider”,
“2kv8X2a9bxnBM8NKLc6BBTX2z13GFNRL4oRotMUJRva9”: “👻 Gh0stee”,
“FxSuDZSxfouRxKH8LqGUHaecvQTrUNUvh9hk3HRAXiGa”: “💋 +70к”,
“BJXjRq566xt66pcxCmCMLPSuNxyUpPNBdJGP56S7fMda”: “📆 NEW-560”,
“FRa5xvWrvgYBHEukozdhJPCJRuJZcTn2WKj2u6L75Rmj”: “📨 206H”,
“BLhQ4fWgkNAJ4MWXSdXaTnxwZxwHh7QTnMQb6i3Z2QYy”: “🌙 90Н”,
“63oQYEauMBFyaGQ69CNkwXFzCvdkFxdPaxGKYx72Tedb”: “🎉 120Н”,
“2HpvvY7TcbSdr8uNrDBUyEvbD9mcjg4ssmWQFcQcwJap”: “🦊 NEW-199”,
“DsqRyTUh1R37asYcVf1KdX4CNnz5DKEFmnXvgT4NfTPE”: “🍗 Classic”,
“EPFDmjJKBX1JrHHpzWRﬀZQv6jeZuo6o3g6FoeKJG5Ha”: “🐆 447Н”,
“5owZXjEe27wZTRevqRUETwia3EctJiaYtKhpqmPzWHuj”: “🎨 +$90.8к”,
“52YXFG9ksGps7P9ZSDLK79f9Hpa5ihR24w6dkikW5aEB”: “👗 49%-30к”,
“8Hw9X9UwBso7Sp2CFnEEeUGW8pGDj9wghc78ccWFZWpU”: “💨 +50k”,
“7SDs3PjT2mswKQ7Zo4FTucn9gJdtuW4jaacPA65BseHS”: “😀 Insentos”,
“CW6XezzEftYw4aALKo96x6oudqBZ3sfVXrfF23hAezdX”: “🦴 295H”,
“EJvokC7vFEubsdEmJX3do1FgfwdUSDYZKGVa5MMs2isA”: “🍄 +40к”,
“4gLZztSiwUnQtbqzc6sJrTjfgA5RCweHgokiLgEWPn3u”: “🦍 +$168К”,
“8rvAsDKeAcEjEkiZMug9k8v1y8mW6gQQiMobd89Uy7qR”: “🎰 casino”,
“DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm”: “🦩 gake”,
“AEtL29wgARtujVynpgoDtUMLvM7NmZ6WALcjD2NjU8Dk”: “🛢 +$166К КИТ”,
“242p259rfsb9J3X3mhnWw35UM2hfMDg14G47CQ66s9ZW”: “💨 NEW-3”,
“2HWT2KLLdN2wxYTqdSuko5SBzg2SEJASgV4GE2tD7TML”: “🏗 164Н”,
“76ZUBj1JLz7arTVHSRJok5oSTEqDuVBgySFMVHtzxzZc”: “❓ +$87.1К”,
“3BLjRcxWGtR7WRshJ3hL25U3RjWr5Ud98wMcczQqk4Ei”: “🙊 Sebastian”,
“77n6X7LtGy5AZprsvjZu1eaekJpxqLeVRZLPJZdBYyg9”: “⭐ 242Н”,
“BCagckXeMChUKrHEd6fKFA1uiWDtcmCXMsqaheLiUPJd”: “🦹 &dv”,
“6S8GezkxYUfZy9JPtYnanbcZTMB87Wjt1qx3c6ELajKC”: “⛷ 184Н”,
“8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs”: “🍶 big bags”,
“AeLaMjzxErZt4drbWVWvcxpVyo8p94xu5vrg41eZPFe3”: “😡 simle”,
“GrXjXop95XkVPYJafDJNCLFzK9K8LkpopxYcgUUn2H87”: “🦁 NEW-189”,
“mW4PZB45isHmnjGkLpJvjKBzVS5NXzTJ8UDyug4gTsM”: “🐺 igndex”,
“XXXXXahGswEH6i3Czn19XbGxQrobJoY1TYJegPxp3ex”: “🦜 +$73.1к”,
“JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN”: “🍃 WEST”,
“EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc”: “🍍 254Н”,
“53BnNc49Ajgstciq3CRoyxuBpkkW1r8pgPyvr7JGYnsh”: “👾 Monki”,
“4nvNc7dDEqKKLM4Sr9Kgk3t1of6f8G66kT64VoC95LYh”: “🐌 а”,
“7aMgK5L4qEQ8Nyv6ZzhZi2B82NSSRnwb2NGJnNagA46D”: “🍿 70%+66к”,
“J6TDXvarvpBdPXTaTU8eJbtso1PUCYKGkVtMKUUY8iEa”: “🧂 +$115к”,
“4SbDMrX8Zfj7qZtRKTBSQEavPkc7BP1kiJfT2f3dn8RL”: “🦈 АКУЛА”,
“8MaVa9kdt3NW4Q5HyNMm1X5LbR8PQRVDc1W8NMVK88D5”: “🏖 Daumen”,
“CLegS2MSiCsBksVazCg4Y7Gz3NqeBK21QyvzK4Q7S168”: “🐝 NEW-13”,
“CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o”: “👽 kentes”,
“5h7yzwmrGoG2BmxNCqNR2EnSv1LWCFo7n6SKSh5ZWkfE”: “🖌 307H”,
“4CqecFud362LKgALvChyhj6276he3Sy8yKim1uvFNV1m”: “🥴 182 H”,
“4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk”: “🦥 GIGO”,
“2C5m99kgdKkiwZCm5qLjpLXrrKAuz1FtM3GoenWkSD8w”: “👠 478 H”,
“3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV”: “🦜 Bastille”,
“9RTva4wSk8E3EWYc8wtF9V94RUQGkemWtt3i8dUtsA4P”: “💤”,
“F7KSBM7SVVYUczJTCLpLJFPDEBrmrfi9ZiGru1BzAuwi”: “🚄 WolfyXBT”,
“Bpk7VVctpzXYx4BuPnZzs3VSSAWSAQJVq9VufFAq5p6b”: “📏 337H”,
“73LnJ7G9ffBDjEBGgJDdgvLUhD5APLonKrNiHsKDCw5B”: “🤪 Waddles”,
“HdxkiXqeN6qpK2YbG51W23QSWj3Yygc1eEk2zwmKJExp”: “🛶 42H”,
“G5nxEXuFMfV74DSnsrSatqCW32F34XUnBeq3PfDS7w5E”: “🎾 72H”,
“FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke”: “🧪 Radiance”,
“5B79fMkcFeRTiwm7ehsZsFiKsC7m7n1Bgv9yLxPp9q2X”: “🐮 bandit”,
“Ez2jp3rwXUbaTx7XwiHGaWVgTPFdzJoSg8TopqbxfaJN”: “🍂 +$313k”,
“niggerd597QYedtvjQDVHZTCCGyJrwHNm2i49dkm5zS”: “🎲 NEW-223”,
“HL3FZ8XWnLnn1HuktmgpNRyFRjuAxWbXNQVj5fPPzZwt”: “🧚”,
“GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65”: “🤑 latuche”,
“G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC”: “📱 clukz”,
“EjaMRoxyHFSLdMtRtXLtinT96mTHhEdp9jubVubwWtxr”: “🦋 ОЛД”,
“A2B76kth3LZB7GK6dSzRcZBYNWsn2K6fCWyKVXBFqKx4”: “🥩 252H”,
“HYWo71Wk9PNDe5sBaRKazPnVyGnQDiwgXCFKvgAQ1ENp”: “🐑 268H”,
“7mGZh58meFf8xsES37bc2hdffEmh8aTDcB2i725Zivyg”: “🎷”,
“DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC”: “🛷 362 H”,
“BQVz7fQ1WsQmSTMY3umdPEPPTm1sdcBcX9sP7o6kPRmB”: “🦀 +41.9K”,
}

# ================= HELPERS =================

def short(addr): return f”{addr[:4]}…{addr[-4:]}”

def emoji(w):
return WALLET_EMOJI.get(w, f”🔹 {short(w)}”)

def hold_percent(wallet, mint):
with lock:
b = ledger[(wallet, mint)][“buy”]
s = ledger[(wallet, mint)][“sell”]
if b <= 0: return 0
return max(0, int(((b - s) / b) * 100))

def status_icon(pct):
“”“🔷 тримає все | 🔶 частково продав | 🔺 вийшов повністю”””
if pct >= 100: return “🔷”
if pct <= 0:   return “🔺”
return “🔶”

def format_mc(mc):
if not mc: return “N/A”
return f”${mc/1_000_000:.2f}M” if mc >= 1_000_000 else f”${mc/1000:.1f}K”

def tx_age_str(ts):
diff = int(time.time() - ts)
if diff < 60:  return f”{diff}s tx”
if diff < 3600: return f”{diff//60}m tx”
return f”{diff//3600}h tx”

def seen_str(first_ts):
diff = int(time.time() - first_ts)
if diff < 60:   return “<1m”
if diff < 3600: return f”{diff//60}m”
return f”{diff//3600}h”

# ================= SYMBOL CACHE =================

def get_symbol(mint):
now = time.time()
if mint in symbol_cache:
sym, ts = symbol_cache[mint]
if now - ts < SYMBOL_TTL:
return sym
try:
r = requests.get(
f”https://api.dexscreener.com/latest/dex/tokens/{mint}”,
timeout=5
).json()
if r.get(“pairs”):
sym = r[“pairs”][0][“baseToken”][“symbol”]
symbol_cache[mint] = (sym, now)
return sym
except Exception as e:
logging.warning(f”get_symbol error {mint[:8]}: {e}”)
return mint[:6]

# ================= MARKET CACHE =================

def get_market(mint):
now = time.time()
if mint in market_cache:
mc, pair, ts = market_cache[mint]
if now - ts < MARKET_TTL:
return mc, pair
try:
r = requests.get(
f”https://api.dexscreener.com/latest/dex/tokens/{mint}”,
timeout=5
).json()
if not r.get(“pairs”):
return 0, None
p = next(
(x for x in r[“pairs”] if x.get(“chainId”) == “solana”),
r[“pairs”][0]
)
mc   = p.get(“fdv”, 0)
pair = p.get(“pairAddress”)
market_cache[mint] = (mc, pair, now)
return mc, pair
except Exception as e:
logging.warning(f”get_market error {mint[:8]}: {e}”)
return 0, None

def get_market_with_retry(mint, retries=2, delay=2):
for attempt in range(retries):
mc, pair = get_market(mint)
if mc > 0:
return mc, pair
if attempt < retries - 1:
time.sleep(delay)
return 0, None

def build_axiom(mint, pair):
return f”https://axiom.trade/meme/{pair if pair else mint}?chain=sol”

# ================= TELEGRAM SEND =================

def send(text, url=None):
payload = {
“chat_id”: CHAT_ID,
“text”: text,
“parse_mode”: “HTML”,
“disable_web_page_preview”: True
}
if url:
payload[“reply_markup”] = {“inline_keyboard”: [[{“text”: “AXIOM”, “url”: url}]]}
try:
requests.post(
f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”,
json=payload, timeout=8
)
except Exception as e:
logging.error(f”TG send error: {e}”)

# ================= BUILD MULTI TEXT =================

def build_multi_text(mint, cl, mcap, sym_name):
“””
Будує текст multi-алерту з актуальними даними всіх гаманців.
Формат як у Memescope:
🔷/🔶/🔺 EmojiName (Xs tx)
├ X.XX SOL | MC $XXX
└ Total buy: X.XX SOL | 👊 XX%
“””
w_count   = len(cl[“wallets”])
total_sol = cl[“total”]
seen      = seen_str(cl[“first_ts”])

```
txt = (
    f"‼️ 🟢 <b>MULTI BUY {sym_name}</b>\n\n"
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
        f"├ <b>{amt:.2f} SOL</b> | MC {format_mc(mcap)}\n"
        f"└ Total buy: {total_buy:.2f} SOL | 👊 {hp}%\n\n"
    )

txt += f"🔗 #{sym_name} | MC: {format_mc(mcap)} | Seen: {seen}\n"
txt += f"<code>{mint}</code>"
return txt
```

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
if now - wallet_agg[k][“first_ts”] > 600:
del wallet_agg[k]
for k in list(clusters):
if now - clusters[k][“first_ts”] > CLUSTER_LIFETIME + 3600:
del clusters[k]
sent_multi.pop(k, None)
for k in list(sent_ordinary):
if now - sent_ordinary[k] > CLUSTER_LIFETIME:
del sent_ordinary[k]
for k in list(ledger):
if now - ledger[k].get(“last_ts”, 0) > 86400:
del ledger[k]
for m in list(symbol_cache):
if now - symbol_cache[m][1] > SYMBOL_TTL * 2:
del symbol_cache[m]
for m in list(market_cache):
if now - market_cache[m][2] > 3600:
del market_cache[m]

```
    logging.info(
        f"[Cleanup] sigs={len(processed_signatures)} "
        f"clusters={len(clusters)} ledger={len(ledger)}"
    )
```

threading.Thread(target=cleanup_loop, daemon=True).start()

# ================= ACTIVE MULTI CHECK =================

def is_active_multi(mint):
if mint not in sent_multi:
return False
if mint in clusters:
if time.time() - clusters[mint][“first_ts”] < CLUSTER_LIFETIME:
return True
return False

# ================= ORDINARY ALERT =================

def delayed_ordinary_send(wallet, mint, key):
now = time.time()
with lock:
if is_active_multi(mint):
logging.info(f”Ordinary suppressed (active multi): {mint[:8]}”)
wallet_agg.pop(key, None)
return
if key not in wallet_agg:
return
final_amt = wallet_agg[key][“amount”]
del wallet_agg[key]
sent_ordinary[key] = now

```
symbol = get_symbol(mint)
if symbol.upper() in STABLE_SYMBOLS:
    return

mc, pair = get_market_with_retry(mint)
ax = build_axiom(mint, pair)
hp = hold_percent(wallet, mint)
total_buy = ledger[(wallet, mint)]["buy"]

logging.info(f"SEND ordinary | {emoji(wallet)} | {symbol} | {final_amt:.2f} SOL")

txt = (
    f"🟢 <b>BUY {symbol}</b>\n\n"
    f"{status_icon(hp)} {emoji(wallet)}\n"
    f"├ <b>{final_amt:.2f} SOL</b> | MC {format_mc(mc)}\n"
    f"└ Total buy: {total_buy:.2f} SOL | 👊 {hp}%\n\n"
    f"<code>{mint}</code>"
)
send(txt, ax)
```

# ================= WEBHOOK =================

@app.route(”/”, methods=[“POST”])
def webhook():
txs = request.json
if not isinstance(txs, list):
return jsonify(ok=True)

```
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

    # Фільтри
    if bought_mint in STABLE_MINTS:
        continue
    symbol = get_symbol(bought_mint)
    if symbol.upper() in STABLE_SYMBOLS:
        continue

    logging.info(f"BUY | {emoji(wallet)} | {symbol} | {sol_abs:.2f} SOL")

    key = (wallet, bought_mint)

    # --- Звичайний алерт ---
    with lock:
        is_recent = key in sent_ordinary and now - sent_ordinary[key] < CLUSTER_LIFETIME
        if not is_recent and not is_active_multi(bought_mint):
            if key not in wallet_agg:
                wallet_agg[key] = {"amount": sol_abs, "first_ts": now, "timer_started": False}
            else:
                wallet_agg[key]["amount"] += sol_abs

            if wallet_agg[key]["amount"] >= MIN_BUY_SOL and not wallet_agg[key]["timer_started"]:
                wallet_agg[key]["timer_started"] = True
                threading.Timer(15.0, delayed_ordinary_send, args=[wallet, bought_mint, key]).start()

    # --- Multi-wallet алерт ---
    if sol_abs >= MULTI_MIN_SOL:
        with lock:
            # Новий кластер якщо старий вичерпався
            if bought_mint not in clusters or now - clusters[bought_mint]["first_ts"] > CLUSTER_LIFETIME:
                clusters[bought_mint] = {
                    "wallets": {},
                    "total": 0.0,
                    "first_ts": now,
                    "sym": symbol
                }

            cl = clusters[bought_mint]

            # Оновлюємо суму якщо гаманець вже є (докупив)
            if wallet in cl["wallets"]:
                cl["wallets"][wallet]["amt"] += sol_abs
                cl["wallets"][wallet]["ts"]   = now
                cl["total"] += sol_abs
            else:
                cl["wallets"][wallet] = {"amt": sol_abs, "ts": now}
                cl["total"] += sol_abs

            w_count        = len(cl["wallets"])
            last_sent_info = sent_multi.get(bought_mint, {"count": 0, "ts": 0})

            # Надсилаємо якщо: вперше досягли порогу АБО додався новий гаманець
            should_send = w_count >= MULTI_MIN_WALLETS and w_count > last_sent_info["count"]

            if should_send:
                sent_multi[bought_mint] = {"count": w_count, "ts": now}

                # Скасовуємо pending ordinary
                for k in list(wallet_agg):
                    if k[1] == bought_mint:
                        del wallet_agg[k]

                snapshot_cl  = {
                    "wallets":  {w: dict(info) for w, info in cl["wallets"].items()},
                    "total":    cl["total"],
                    "first_ts": cl["first_ts"],
                    "sym":      cl.get("sym", symbol)
                }
                snap_mint    = bought_mint
                snap_symbol  = symbol

                def send_multi_alert(m, snap, sym_name):
                    mcap, pr = get_market_with_retry(m)
                    ax_url   = build_axiom(m, pr)
                    txt      = build_multi_text(m, snap, mcap, sym_name)
                    logging.info(
                        f"SEND multi | {sym_name} | {len(snap['wallets'])} wallets | "
                        f"{snap['total']:.2f} SOL | MC {format_mc(mcap)}"
                    )
                    send(txt, ax_url)

                threading.Thread(
                    target=send_multi_alert,
                    args=[snap_mint, snapshot_cl, snap_symbol]
                ).start()

return jsonify(ok=True)
```

if **name** == “**main**”:
app.run(host=“0.0.0.0”, port=int(os.getenv(“PORT”, 10000)))
