import sys

LIMIT = 10 ** 12


def parse_amount(s):
    if not s:
        return None
    for c in s:
        if c < '0' or c > '9':
            return None
    t = s.lstrip('0')
    if t == '':
        return 0
    if len(t) > 13:
        return None
    v = int(t)
    if v > LIMIT:
        return None
    return v


def main():
    data = sys.stdin.read()
    bal = {}
    bad = 0
    for line in data.split('\n'):
        toks = line.split()
        if not toks:
            continue
        if len(toks) < 3:
            bad += 1
            continue
        payer = toks[0]
        amt = parse_amount(toks[1])
        if amt is None:
            bad += 1
            continue
        parts = toks[2:]
        if len(set(parts)) != len(parts):
            bad += 1
            continue
        k = len(parts)
        q, r = divmod(amt, k)
        bal[payer] = bal.get(payer, 0) + amt
        for i in range(k):
            p = parts[i]
            owe = q + 1 if i < r else q
            bal[p] = bal.get(p, 0) - owe
    out = []
    out.append("bad %d\n" % bad)
    total = 0
    for name in sorted(bal.keys()):
        v = bal[name]
        total += v
        out.append("balance " + name + " " + str(v) + "\n")
    out.append("total %d\n" % total)
    sys.stdout.write("".join(out))


main()
