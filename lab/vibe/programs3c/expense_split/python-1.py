import re
import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
    splitter = re.compile(r"[ \t\r\v\f]+")
    bad = 0
    bal = {}

    for raw in data.split("\n"):
        toks = [t for t in splitter.split(raw) if t]
        if not toks:
            continue
        if len(toks) < 3:
            bad += 1
            continue

        payer = toks[0]
        amt_s = toks[1]
        parts = toks[2:]

        if not amt_s or not all("0" <= c <= "9" for c in amt_s):
            bad += 1
            continue
        amt = int(amt_s)
        if amt > 10**12:
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

    out = [f"bad {bad}\n"]
    total = 0
    for name in sorted(bal):
        v = bal[name]
        total += v
        out.append(f"balance {name} {v}\n")
    out.append(f"total {total}\n")

    sys.stdout.buffer.write("".join(out).encode("utf-8", "surrogateescape"))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
