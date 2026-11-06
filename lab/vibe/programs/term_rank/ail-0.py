import sys


DIGIT_VALUE = {}
for _c in "0123456789":
    DIGIT_VALUE[_c] = len(DIGIT_VALUE)


def is_word(b):
    return (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b >= 128


STOP_WORDS = set()
for _w in (
    "an and are as at be but by for from had has have he her his in into is it its "
    "not of on or our she so than that the their them then there these they this to "
    "was we were which will with you your"
).split():
    STOP_WORDS.add(_w.encode())


def tokenize_line(line):
    res = []
    cur = bytearray()
    n = len(line)
    i = 0
    while i < n:
        b = line[i]
        if is_word(b):
            cur.append(b)
        elif b == 39 or b == 45:
            if cur and i + 1 < n and is_word(line[i + 1]):
                cur.append(b)
            elif cur:
                res.append(bytes(cur))
                cur = bytearray()
        else:
            if cur:
                res.append(bytes(cur))
                cur = bytearray()
        i += 1
    if cur:
        res.append(bytes(cur))
    return res


def make_term(tok):
    t = tok.replace(b"'", b"")
    ba = bytearray(t)
    for i in range(len(ba)):
        c = ba[i]
        if 65 <= c <= 90:
            ba[i] = c + 32
    t = bytes(ba)
    if len(t) > 0:
        alldig = True
        for c in t:
            if c < 48 or c > 57:
                alldig = False
                break
        if alldig:
            return b"#" + str(len(t)).encode()
    if len(t) < 2:
        return None
    if t in STOP_WORDS:
        return None
    if len(t) >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]
    return t


def main():
    argv = sys.argv
    if len(argv) != 2:
        sys.exit(1)
    a = argv[1]
    for c in a:
        if c not in DIGIT_VALUE:
            sys.exit(1)

    j = 0
    while j < len(a) and a[j] == "0":
        j += 1
    if j >= len(a):
        sys.exit(1)
    if len(a) - j > 4:
        sys.exit(1)
    k = 0
    while j < len(a):
        k = k * 10 + DIGIT_VALUE[a[j]]
        j += 1
    if k < 1 or k > 1000:
        sys.exit(1)

    data = sys.stdin.buffer.read()
    if len(data) == 0:
        lines = []
    else:
        lines = data.split(b"\n")
        if data.endswith(b"\n"):
            lines.pop()

    docs = [[]]
    for ln in lines:
        if ln == b"%%" or ln == b"%%\r":
            docs.append([])
        else:
            docs[-1].append(ln)

    N = len(docs)
    doc_counts = []
    df = {}
    total = {}
    for doc in docs:
        cnt = {}
        for ln in doc:
            for tok in tokenize_line(ln):
                t = make_term(tok)
                if t is None:
                    continue
                if t in cnt:
                    cnt[t] += 1
                else:
                    cnt[t] = 1
        doc_counts.append(cnt)
        for t, c in cnt.items():
            if t in df:
                df[t] += 1
            else:
                df[t] = 1
            if t in total:
                total[t] += c
            else:
                total[t] = c

    out = []
    for idx in range(N):
        cnt = doc_counts[idx]
        items = []
        for t, tf in cnt.items():
            s = tf * 1000 * (N + 1) // (df[t] * (tf + 2))
            items.append((t, s))
        items.sort(key=lambda p: (-p[1], p[0]))
        if len(items) > k:
            items = items[:k]
        parts = [b"doc ", str(idx + 1).encode(), b":"]
        for t, s in items:
            parts.append(b" ")
            parts.append(t)
            parts.append(b"=")
            parts.append(str(s).encode())
        out.append(b"".join(parts))

    items = []
    for t, c in total.items():
        items.append((t, c))
    items.sort(key=lambda p: (-p[1], p[0]))
    if len(items) > k:
        items = items[:k]
    parts = [b"all:"]
    for t, c in items:
        parts.append(b" ")
        parts.append(t)
        parts.append(b"=")
        parts.append(str(c).encode())
    out.append(b"".join(parts))

    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
