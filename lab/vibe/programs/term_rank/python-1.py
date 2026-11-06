import sys
from collections import Counter

STOP = set(
    w.encode() for w in (
        "an and are as at be but by for from had has have he her his in into is it its "
        "not of on or our she so than that the their them then there these they this to "
        "was we were which will with you your"
    ).split()
)


def is_word(b):
    return (65 <= b <= 90) or (97 <= b <= 122) or (48 <= b <= 57) or (b >= 128)


def is_joiner(b):
    return b == 39 or b == 45


def transform(tok):
    t = tok.replace(b"'", b"")
    t = bytes((c + 32 if 65 <= c <= 90 else c) for c in t)
    if t and all(48 <= c <= 57 for c in t):
        t = b"#" + str(len(t)).encode()
    if len(t) < 2:
        return None
    if t in STOP:
        return None
    if len(t) >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]
    return t


def tokenize(line):
    i = 0
    L = len(line)
    while i < L:
        if is_word(line[i]):
            j = i + 1
            while j < L:
                if is_word(line[j]):
                    j += 1
                elif is_joiner(line[j]) and j + 1 < L and is_word(line[j + 1]):
                    j += 2
                else:
                    break
            yield line[i:j]
            i = j
        else:
            i += 1


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        sys.exit(1)
    s = args[0]
    if not s or any(c not in "0123456789" for c in s):
        sys.exit(1)
    k = int(s)
    if k < 1 or k > 1000:
        sys.exit(1)

    data = sys.stdin.buffer.read()

    if data == b"":
        lines = []
    else:
        lines = data.split(b"\n")
        if data.endswith(b"\n"):
            lines.pop()

    docs = [[]]
    for line in lines:
        if line == b"%%" or line == b"%%\r":
            docs.append([])
        else:
            docs[-1].append(line)

    N = len(docs)
    doc_counts = []
    df = Counter()
    total = Counter()

    for dlines in docs:
        c = Counter()
        for line in dlines:
            for raw in tokenize(line):
                term = transform(raw)
                if term is not None:
                    c[term] += 1
        doc_counts.append(c)
        for t in c:
            df[t] += 1
        total.update(c)

    out = []

    for idx, c in enumerate(doc_counts, 1):
        items = []
        for t, tf in c.items():
            score = tf * 1000 * (N + 1) // (df[t] * (tf + 2))
            items.append((-score, t))
        items.sort()
        items = items[:k]
        if items:
            parts = [t + b"=" + str(-sc).encode() for sc, t in items]
            out.append(b"doc %d: " % idx + b" ".join(parts) + b"\n")
        else:
            out.append(b"doc %d:\n" % idx)

    items = sorted((-cnt, t) for t, cnt in total.items())
    items = items[:k]
    if items:
        parts = [t + b"=" + str(-cnt).encode() for cnt, t in items]
        out.append(b"all: " + b" ".join(parts) + b"\n")
    else:
        out.append(b"all:\n")

    sys.stdout.buffer.write(b"".join(out))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
