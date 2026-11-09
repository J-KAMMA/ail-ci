import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8", "replace")
    bal = {}
    bad = 0
    digits = "0123456789"

    for line in data.split("\n"):
        toks = line.split()
        if not toks:
            continue
        if len(toks) < 3:
            bad += 1
            continue

        payer = toks[0]
        amt_s = toks[1]
        parts = toks[2:]

        if len(amt_s) == 0:
            bad += 1
            continue
        valid = True
        for c in amt_s:
            if c not in digits:
                valid = False
                break
        if not valid:
            bad += 1
            continue

        stripped = amt_s.lstrip("0")
        if len(stripped) > 13:
            bad += 1
            continue
        amt = int(stripped) if len(stripped) > 0 else 0
        if amt > 1000000000000:
            bad += 1
            continue

        if len(set(parts)) != len(parts):
            bad += 1
            continue

        k = len(parts)
        q, r = divmod(amt, k)
        bal[payer] = bal.get(payer, 0) + amt
        for i, p in enumerate(parts):
            owe = q + 1 if i < r else q
            bal[p] = bal.get(p, 0) - owe

    out = ["bad " + str(bad) + "\n"]
    for name in sorted(bal.keys()):
        out.append("balance " + name + " " + str(bal[name]) + "\n")
    total = 0
    for v in bal.values():
        total += v
    out.append("total " + str(total) + "\n")

    sys.stdout.write("".join(out))


main()
