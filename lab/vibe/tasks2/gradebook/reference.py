"""Reference implementation of gradebook (see spec.md): reference.py < rows"""
import sys

MAXS = 1000000000000


def parse_score(s):
    if not s or any(c < '0' or c > '9' for c in s):
        return None
    v = int(s)
    return v if v <= MAXS else None


def main():
    text = sys.stdin.buffer.read().decode('utf8')
    bad = 0
    stats = {}
    for line in text.split('\n'):
        toks = line.split()
        if not toks:
            continue
        if len(toks) != 3:
            bad += 1
            continue
        name, _assignment = toks[0], toks[1]
        score = parse_score(toks[2])
        if score is None:
            bad += 1
            continue
        c, s = stats.get(name, (0, 0))
        stats[name] = (c + 1, s + score)
    out = ['bad %d' % bad]
    rows = [(s // c, name, c, s) for name, (c, s) in stats.items()]
    rows.sort(key=lambda r: (-r[0], r[1]))
    for avg, name, c, s in rows:
        out.append('%s count %d sum %d avg %d' % (name, c, s, avg))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
