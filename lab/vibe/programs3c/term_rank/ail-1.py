import sys

WORD_STOP = set([
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by", b"for", b"from",
    b"had", b"has", b"have", b"he", b"her", b"his", b"in", b"into", b"is", b"it",
    b"its", b"not", b"of", b"on", b"or", b"our", b"she", b"so", b"than", b"that",
    b"the", b"their", b"them", b"then", b"there", b"these", b"they", b"this", b"to",
    b"was", b"we", b"were", b"which", b"will", b"with", b"you", b"your",
])


def is_word(b):
    return (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b >= 128


def is_joiner(b):
    return b == 39 or b == 45


def normalize(token):
    t = token.replace(b"'", b"")
    t = t.lower()
    if t.isdigit():
        t = b"#" + str(len(t)).encode()
    if len(t) < 2:
        return None
    if t in WORD_STOP:
        return None
    if len(t) >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]
    return t


def line_terms(line):
    res = []
    n = len(line)
    i = 0
    while i < n:
        if is_word(line[i]):
            j = i + 1
            while True:
                while j < n and is_word(line[j]):
                    j += 1
                if j + 1 < n and is_joiner(line[j]) and is_word(line[j + 1]):
                    j += 1
                else:
                    break
            term = normalize(line[i:j])
            if term is not None:
                res.append(term)
            i = j
        else:
            i += 1
    return res


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        sys.exit(1)
    s = args[0]
    if len(s) == 0:
        sys.exit(1)
    for ch in s:
        if ch not in "0123456789":
            sys.exit(1)
    K = int(s)
    if K < 1 or K > 1000:
        sys.exit(1)

    data = sys.stdin.buffer.read()
    if len(data) == 0:
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

    tfs = []
    df = {}
    total = {}
    for doc in docs:
        tf = {}
        for line in doc:
            for t in line_terms(line):
                tf[t] = tf.get(t, 0) + 1
        tfs.append(tf)
        for t, c in tf.items():
            df[t] = df.get(t, 0) + 1
            total[t] = total.get(t, 0) + c

    out = []
    for d in range(1, N + 1):
        tf = tfs[d - 1]
        scored = []
        for t, c in tf.items():
            sc = (c * 1000 * (N + 1)) // (df[t] * (c + 2))
            scored.append((t, sc))
        scored.sort(key=lambda x: (-x[1], x[0]))
        top = scored[:K]
        parts = [b"doc ", str(d).encode(), b":"]
        for t, sc in top:
            parts.append(b" ")
            parts.append(t)
            parts.append(b"=")
            parts.append(str(sc).encode())
        parts.append(b"\n")
        out.append(b"".join(parts))

    items = list(total.items())
    items.sort(key=lambda x: (-x[1], x[0]))
    top = items[:K]
    parts = [b"all:"]
    for t, c in top:
        parts.append(b" ")
        parts.append(t)
        parts.append(b"=")
        parts.append(str(c).encode())
    parts.append(b"\n")
    out.append(b"".join(parts))

    sys.stdout.buffer.write(b"".join(out))
    sys.exit(0)


main()
