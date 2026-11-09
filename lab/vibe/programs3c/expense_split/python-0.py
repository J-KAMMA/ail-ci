import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8", errors="surrogateescape")
    bad = 0
    bal = {}
    limit = 10 ** 12

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

        if not (amt_s.isascii() and amt_s.isdigit()):
            bad += 1
            continue
        digits = amt_s.lstrip("0") or "0"
        if len(digits) > 13:
            bad += 1
            continue
        amount = int(digits)
        if amount > limit:
            bad += 1
            continue

        if len(set(parts)) != len(parts):
            bad += 1
            continue

        k = len(parts)
        q, r = divmod(amount, k)

        bal[payer] = bal.get(payer, 0) + amount
        for i, p in enumerate(parts):
            owe = q + 1 if i < r else q
            bal[p] = bal.get(p, 0) - owe

    out = []
    out.append("bad %d\n" % bad)
    for name in sorted(bal.keys()):
        out.append("balance %s %d\n" % (name, bal[name]))
    total = sum(bal.values())
    out.append("total %d\n" % total)

    sys.stdout.buffer.write("".join(out).encode("utf-8", errors="surrogateescape"))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
