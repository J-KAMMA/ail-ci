"""Reference implementation of term_rank (see spec.md): reference.py K < text"""
import heapq
import re
import sys
from collections import Counter

RAW = re.compile(rb"[A-Za-z0-9\x80-\xff]+(?:['-][A-Za-z0-9\x80-\xff]+)*")
DIGITS = re.compile(rb'[0-9]+')
STOP = set(b'''an and are as at be but by for from had has have he her his in into is it its not of on or
our she so than that the their them then there these they this to was we were which will with
you your'''.split())
UPPER = bytes.maketrans(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ', b'abcdefghijklmnopqrstuvwxyz')


def to_term(raw):
    t = raw.replace(b"'", b'').translate(UPPER)
    if DIGITS.fullmatch(t):
        t = b'#%d' % len(t)
    if len(t) < 2 or t in STOP:
        return None
    if len(t) >= 5 and t.endswith(b'ing'):
        return t[:-3]
    if len(t) >= 4 and t.endswith(b's') and not t.endswith(b'ss'):
        return t[:-1]
    return t


def main(argv):
    if len(argv) != 2 or not re.fullmatch(r'[0-9]+', argv[1]) or not 1 <= int(argv[1]) <= 1000:
        return 1
    k = int(argv[1])
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    docs = []
    cur = []
    for line in lines:
        if line == b'%%' or line == b'%%\r':
            docs.append(b'\n'.join(cur))
            cur = []
        else:
            cur.append(line)
    docs.append(b'\n'.join(cur))
    cache = {}
    counts = []
    df = Counter()
    total = Counter()
    for doc in docs:
        c = Counter()
        for raw in RAW.findall(doc):
            t = cache.get(raw, 0)
            if t == 0:
                t = cache[raw] = to_term(raw)
            if t is not None:
                c[t] += 1
        counts.append(c)
        df.update(c.keys())
        total.update(c)
    n = len(docs)
    out = []
    for i, c in enumerate(counts):
        scored = ((-(tf * 1000 * (n + 1) // (df[t] * (tf + 2))), t) for t, tf in c.items())
        best = heapq.nsmallest(k, scored)
        out.append(b'doc %d:' % (i + 1) + b''.join(b' %s=%d' % (t, -s) for s, t in best))
    best = heapq.nsmallest(k, ((-v, t) for t, v in total.items()))
    out.append(b'all:' + b''.join(b' %s=%d' % (t, -v) for v, t in best))
    sys.stdout.buffer.write(b'\n'.join(out) + b'\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
