import sys
import re
import heapq
from collections import Counter

STOP = set(b"""an and are as at be but by for from had has have he her his in into is it its not of on or
our she so than that the their them then there these they this to was we were which will with
you your""".split())

TOK = re.compile(rb"[0-9A-Za-z\x80-\xff]+(?:['-][0-9A-Za-z\x80-\xff]+)*")
UP = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")
cache = {}


def conv(tok):
    t = tok.replace(b"'", b"").translate(UP)
    if t.isdigit():
        t = b"#" + str(len(t)).encode()
    if len(t) < 2 or t in STOP:
        return None
    n = len(t)
    if n >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif n >= 4 and t[-1:] == b"s" and not t.endswith(b"ss"):
        t = t[:-1]
    return t


def main():
    a = sys.argv[1:]
    if len(a) != 1 or not re.fullmatch(r"[0-9]+", a[0]) or not (1 <= int(a[0]) <= 1000):
        sys.exit(1)
    K = int(a[0])
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    docs = [[]]
    for ln in lines:
        if ln == b"%%" or ln == b"%%\r":
            docs.append([])
        else:
            docs[-1].append(ln)
    N = len(docs)
    counters = []
    df = Counter()
    total = Counter()
    for d in docs:
        c = Counter()
        for ln in d:
            for tok in TOK.findall(ln):
                if tok in cache:
                    t = cache[tok]
                else:
                    t = cache[tok] = conv(tok)
                if t is not None:
                    c[t] += 1
        counters.append(c)
        df.update(c.keys())
        total.update(c)
    out = []
    for i, c in enumerate(counters, 1):
        items = [(-(tf * 1000 * (N + 1) // (df[t] * (tf + 2))), t) for t, tf in c.items()]
        best = heapq.nsmallest(K, items)
        line = b"doc %d:" % i
        if best:
            line += b" " + b" ".join(t + b"=%d" % -s for s, t in best)
        out.append(line)
    best = heapq.nsmallest(K, ((-n, t) for t, n in total.items()))
    line = b"all:"
    if best:
        line += b" " + b" ".join(t + b"=%d" % -s for s, t in best)
    out.append(line)
    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
