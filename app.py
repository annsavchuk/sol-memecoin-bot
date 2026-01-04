import os
import time
from decimal import Decimal, ROUND_DOWN
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ====== CONFIG ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

MIN_SOL = Decimal("4.00")
AGG_WINDOW = 6 * 60 * 60      # 6 hours
DEBOUNCE = 120                # 2 minutes
LAMPORTS_PER_SOL = Decimal("1000000000")

SOL_MINT = "So11111111111111111111111111111111111111112"
STABLE_KEYWORDS = ("usd", "usdt", "usdc", "uxd", "dai", "busd")  # exclude if token mint string contains any of these

# ====== STATE ======
# STATE[token_mint] = {
#   "start": ts,
#   "wallets": { wallet_addr: {"total": Decimal, "last": Decimal} },
#   "last_alert": ts
# }
STATE = {}

# ====== HELPERS ======
def now_ts():
    return int(time.time())

def short_addr(a: str):
    if not a or len(a) < 12:
        return a
    return f"{a[:6]}…{a[-4:]}"

def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_TOKEN/CHAT_ID not set.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print("Telegram error", r.status_code, r.text)
    except Exception as e:
        print("Telegram send exception:", e)

def quantize_sol(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

def fmt_sol(d: Decimal) -> str:
    # format with thousands separator and 2 decimals
    return f"{d:,.2f}"

def is_stable_mint(mint: str) -> bool:
    if not mint:
        return False
    m = mint.lower()
    return any(k in m for k in STABLE_KEYWORDS)

# ====== PARSERS ======
def find_buyer(tx: dict):
    # Priority: feePayer -> userAccount -> tokenTransfers.toUserAccount -> nativeTransfers.fromUserAccount
    buyer = tx.get("feePayer") or tx.get("userAccount")
    if buyer:
        return buyer

    for t in tx.get("tokenTransfers", []):
        if t.get("toUserAccount"):
            return t.get("toUserAccount")
    for n in tx.get("nativeTransfers", []):
        if n.get("fromUserAccount"):
            return n.get("fromUserAccount")
    return None

def find_bought_token(tx: dict, buyer: str):
    # Prefer tokenTransfers where toUserAccount == buyer and mint is not SOL and not stable
    cand = None
    max_amt = Decimal("0")
    for t in tx.get("tokenTransfers", []):
        if t.get("toUserAccount") == buyer:
            mint = t.get("mint")
            try:
                amt = Decimal(str(t.get("tokenAmount", 0)))
            except Exception:
                amt = Decimal("0")
            if not mint:
                continue
            if mint == SOL_MINT or is_stable_mint(mint):
                continue
            # choose transfer with largest tokenAmount for buyer
            if amt >= max_amt:
                max_amt = amt
                cand = mint
    if cand:
        return cand

    # fallback: check swap-like structures (tokenOutputs)
    swap = tx.get("swap") or tx.get("swaps") or tx.get("parsedSwaps") or tx.get("swapInfo")
    if swap:
        swaps = swap if isinstance(swap, list) else [swap]
        for s in swaps:
            token_outputs = s.get("tokenOutputs") or s.get("tokenOutputs", [])
            if token_outputs and isinstance(token_outputs, list):
                for out in token_outputs:
                    mint = out.get("mint")
                    if mint and mint != SOL_MINT and not is_stable_mint(mint):
                        return mint
    return None

def extract_real_swap_sol(tx: dict, token_mint: str, buyer: str):
    """
    Try to extract the real SOL input amount for buying token_mint by buyer.
    Prefer structured 'swap' entries (inAmount/nativeInput). Fallback to
    summing nativeTransfers from buyer (less accurate).
    Returns Decimal SOL (rounded down to 2 decimals) or Decimal('0.00').
    """
    # Try structured swap blocks
    swap_keys = ["swap", "swaps", "parsedSwaps", "swapInfo", "swapEvents"]
    amount_keys = ["inAmount", "inputAmount", "nativeInput", "nativeInputAmount", "amountIn", "amount"]
    for key in swap_keys:
        swaps = tx.get(key)
        if not swaps:
            continue
        if isinstance(swaps, dict):
            swaps = [swaps]
        for sw in swaps:
            if not isinstance(sw, dict):
                continue
            # determine output mint
            out_mint = None
            # common shapes:
            # sw.get("outputMint") or sw.get("outMint") or sw.get("tokenOutputs")
            out_mint = sw.get("outputMint") or sw.get("outMint")
            if not out_mint:
                token_outputs = sw.get("tokenOutputs") or sw.get("tokenOutputs", [])
                if token_outputs and isinstance(token_outputs, list) and len(token_outputs) > 0:
                    out_mint = token_outputs[0].get("mint")
            # some structures use tokenOutputs with index matching buyer etc - we keep simple
            if not out_mint:
                continue
            if out_mint != token_mint:
                continue
            # ensure input mint is SOL or nativeInput exists
            in_mint = sw.get("inputMint") or sw.get("inMint") or sw.get("nativeInputMint")
            # if inputMint exists and is not SOL, skip
            if in_mint and in_mint != SOL_MINT:
                continue
            # find amount
            for akey in amount_keys:
                val = sw.get(akey)
                if val is None:
                    continue
                try:
                    lamports = Decimal(str(val))
                except Exception:
                    continue
                sol = lamports / LAMPORTS_PER_SOL
                sol = quantize_sol(sol)
                return sol

    # Fallback: there may be 'nativeInput' at top-level
    # direct fields
    for top_key in ("nativeInput", "native_input", "nativeAmount"):
        val = tx.get(top_key)
        if val:
            try:
                lamports = Decimal(str(val))
                sol = lamports / LAMPORTS_PER_SOL
                return quantize_sol(sol)
            except Exception:
                pass

    # Last resort: sum nativeTransfers where fromUserAccount == buyer and try to exclude tiny fee recipients
    lamports_sum = Decimal("0")
    for n in tx.get("nativeTransfers", []):
        try:
            amt = Decimal(str(n.get("amount", 0)))
        except Exception:
            amt = Decimal("0")
        # only count moves from buyer
        if n.get("fromUserAccount") == buyer:
            lamports_sum += abs(amt)
    if lamports_sum <= 0:
        return Decimal("0.00")
    sol = lamports_sum / LAMPORTS_PER_SOL
    return quantize_sol(sol)

# ====== ROUTE ======
@app.route("/", methods=["POST"])
def webhook():
    payload = request.json
    if not payload:
        return jsonify(ok=True)
    # payload is expected to be a list of tx events
    if not isinstance(payload, list):
        # sometimes Helius sends a single dict
        payload = [payload]

    for tx in payload:
        try:
            tx_type = tx.get("type")
            # accept SWAP or missing type (be permissive)
            if tx_type and tx_type.upper() != "SWAP":
                continue

            buyer = find_buyer(tx)
            if not buyer:
                # cannot determine buyer -> skip
                print("[DEBUG] no buyer found for tx")
                continue

            bought_token = find_bought_token(tx, buyer)
            if not bought_token:
                # nothing recognized as bought token
                print(f"[DEBUG] no bought token for buyer={buyer}")
                continue

            # ignore if token appears stable or is SOL mint
            if bought_token == SOL_MINT or is_stable_mint(bought_token):
                print(f"[DEBUG] ignored token {bought_token}")
                continue

            # extract real swap SOL (prefer swap inAmount)
            last_buy = extract_real_swap_sol(tx, bought_token, buyer)
            if last_buy <= Decimal("0.00"):
                print(f"[DEBUG] no swap SOL found for token={bought_token}, buyer={buyer}")
                continue

            if last_buy < MIN_SOL:
                print(f"[DEBUG] last_buy {last_buy} < MIN_SOL, skip")
                continue

            ts = now_ts()

            bucket = STATE.get(bought_token)
            if not bucket or ts - bucket["start"] > AGG_WINDOW:
                bucket = {
                    "start": ts,
                    "wallets": {},      # wallet -> {"total": Decimal, "last": Decimal}
                    "last_alert": 0
                }
                STATE[bought_token] = bucket

            # if buyer already present, update totals but DO NOT trigger alert
            if buyer in bucket["wallets"]:
                # update wallet totals (we store last and total)
                w = bucket["wallets"][buyer]
                w["total"] = quantize_sol(w["total"] + last_buy)
                w["last"] = last_buy
                bucket["start"] = bucket["start"]  # no change
                print(f"[DEBUG] updated existing wallet {buyer} total={w['total']}, last={w['last']}")
                continue

            # New wallet -> add
            bucket["wallets"][buyer] = {"total": quantize_sol(last_buy), "last": last_buy}
            bucket["start"] = bucket.get("start", ts)

            # debounce
            if ts - bucket.get("last_alert", 0) < DEBOUNCE:
                print("[DEBUG] debounce active, skipping alert send")
                continue

            # prepare and send alert
            bucket["last_alert"] = ts
            total_all = quantize_sol(sum(w["total"] for w in bucket["wallets"].values()))

            lines = []
            lines.append("🔥 <b>MULTI BUY ALERT</b>\n")
            lines.append(f"🪙 <b>Token:</b>\n<code>{bought_token}</code>\n")
            lines.append(f"👥 <b>Wallets:</b> {len(bucket['wallets'])}")
            lines.append(f"💰 <b>Total SOL:</b> {fmt_sol(total_all)}\n")

            # each wallet: show last buy and total
            i = 1
            for w_addr, vals in bucket["wallets"].items():
                last = quantize_sol(vals.get("last", Decimal("0.00")))
                total = quantize_sol(vals.get("total", Decimal("0.00")))
                lines.append(f"{i}. <code>{short_addr(w_addr)}</code> → last: {fmt_sol(last)} SOL (total: {fmt_sol(total)} SOL)")
                i += 1

            # Axiom link to specific token
            ax = f"https://axiom.trade/token/{bought_token}"
            lines.append("\n🔗 <a href='" + ax + "'>Open in Axiom</a>")

            message = "\n".join(lines)
            send_telegram(message)
            print(f"[INFO] alert sent token={bought_token} wallets={len(bucket['wallets'])} total={total_all}")

        except Exception as e:
            # never let one tx crash the loop
            print("Exception while processing tx:", e)

    return jsonify(ok=True)

# ====== HEALTH ======
@app.route("/", methods=["GET"])
def home():
    return "OK"

# ====== RUN ======
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in env. Bot will run but cannot send messages.")
    print("Starting app on port", PORT)
    app.run(host="0.0.0.0", port=PORT)
