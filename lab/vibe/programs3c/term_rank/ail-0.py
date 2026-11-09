import sys

STOP = set(b"""an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your""".split())


def is_word(c):
    return (48 <= c <= 57) or (65 <= c <= 90) or (97 <= c <= 122) or c >= 128


def is_joiner(c):
    return c == 39 or c == 45


def tokens(line):
    n = len(line)
    out = []
    i = 0
    while i < n:
        if not is_word(line[i]):
            i += 1
            continue
        j = i + 1
        while j < n:
            c = line[j]
            if is_word(c):
                j += 1
            elif is_joiner(c) and j + 1 < n and is_word(line[j + 1]):
                j += 1
            else:
                break
        out.append(line[i:j])
        i = j
    return out


def term_of(tok):
    t = tok.replace(b"'", b"").lower()
    if t.isdigit():
        t = b"#" + str(len(t)).encode()
    if len(t) < 2:
        return None
    if t in STOP:
        return None
    n = len(t)
    if n >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif n >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]
    return t


def usage_fail():
    sys.exit(1)


def main():
    args = sys.argv
    if len(args) != 2:
        usage_fail()
    s = args[1]
    if len(s) == 0:
        usage_fail()
    for ch in s:
        if ch not in "0123456789":
            usage_fail()
    t = s.lstrip("0")
    if len(t) == 0 or len(t) > 4:
        usage_fail()
    K = int(t)
    if K < 1 or K > 1000:
        usage_fail()

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
    doc_tf = []
    df = {}
    total = {}
    for d in docs:
        tf = {}
        for ln in d:
            for tok in tokens(ln):
                t = term_of(tok)
                if t is not None:
                    tf[t] = tf.get(t, 0) + 1
        doc_tf.append(tf)
        for t, c in tf.items():
            df[t] = df.get(t, 0) + 1
            total[t] = total.get(t, 0) + c

    out = []
    for idx in range(N):
        tf = doc_tf[idx]
        scored = []
        for t, c in tf.items():
            sc = c * 1000 * (N + 1) // (df[t] * (c + 2))
            scored.append((-sc, t))
        scored.sort()
        items = scored[:K]
        line = b"doc " + str(idx + 1).encode() + b":"
        if items:
            pieces = [t + b"=" + str(-negsc).encode() for negsc, t in items]
            line += b" " + b" ".join(pieces)
        out.append(line + b"\n")

    ranked = []
    for t, c in total.items():
        ranked.append((-c, t))
    ranked.sort()
    items = ranked[:K]
    line = b"all:"
    if items:
        pieces = [t + b"=" + str(-negc).encode() for negc, t in items]
        line += b" " + b" ".join(pieces)
    out.append(line + b"\n")

    sys.stdout.buffer.write(b"".join(out))
    sys.stdout.flush()
    sys.exit(0)


main()
