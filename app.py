@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    if not data:
        return jsonify({"ok": True})

    # ---- SAFE PAYLOAD NORMALIZATION ----
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events", [])
    else:
        return jsonify({"ok": True})

    if not events:
        return jsonify({"ok": True})

    for tx in events:
        try:
            # -------- SAFE PARSING --------
            wallet = tx.get("signer")
            token = tx.get("tokenMint")
            symbol = tx.get("tokenSymbol")

            raw_amount = tx.get("nativeAmount")
            if raw_amount is None:
                continue

            try:
                sol_amount = float(raw_amount)
            except:
                continue

            # -------- FILTERS --------
            if sol_amount <= 0:
                continue

            # ❌ не реагуємо на SOL
            if token == SOL_MINT or symbol == "SOL":
                continue

            # ❌ не реагуємо на стейбли
            if symbol in STABLECOINS:
                continue

            if not wallet or not token:
                continue

            # -------- BUFFER LOGIC --------
            key = f"{wallet}|{token}"

            if key not in buffers:
                buffers[key] = {
                    "wallet": wallet,
                    "token": token,
                    "total": sol_amount,
                    "count": 1
                }

                threading.Thread(
                    target=flush_alert,
                    args=(key,),
                    daemon=True
                ).start()
            else:
                buffers[key]["total"] += sol_amount
                buffers[key]["count"] += 1

        except Exception as e:
            print("TX parse error:", e)

    return jsonify({"ok": True})
