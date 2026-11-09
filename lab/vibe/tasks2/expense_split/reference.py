"""Reference implementation of expense_split (see spec.md): reference.py < input"""
import sys


def parse_amount(s):
    if not s or any(c < '0' or c > '9' for c in s):
        return None
    v = int(s)
    return v if 0 <= v <= 1000000000000 else None


def main():
    data = sys.stdin.buffer.read().decode('utf8')
    bad = 0
    net = {}
    for line in data.split('\n'):
        toks = line.split()
        if not toks:
            continue
        if len(toks) < 3:
            bad += 1
            continue
        payer, amt_s = toks[0], toks[1]
        people = toks[2:]
        amount = parse_amount(amt_s)
        if amount is None or len(set(people)) != len(people):
            bad += 1
            continue
        q, r = divmod(amount, len(people))
        net[payer] = net.get(payer, 0) + amount
        for i, p in enumerate(people):
            net[p] = net.get(p, 0) - (q + (1 if i < r else 0))
    out = ['bad %d' % bad]
    for name in sorted(net):
        out.append('balance %s %d' % (name, net[name]))
    out.append('total %d' % sum(net.values()))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
