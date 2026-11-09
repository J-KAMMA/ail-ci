import re
import sys

STOP = set(b"an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your".split())

WORD = bytearray(256)
for _c in range(256):
    if (48 <= _c <= 57) or (65 <= _c <= 90) or (97 <= _c <= 122) or _c >= 128:
        WORD[_c] = 1


def tokens(line):
    n = len(line)
    out = []
    i = 0
    while i < n:
        if not WORD[line[i]]:
            i += 1
            continue
        j = i + 1
        while j < n:
            c = line[j]
            if WORD[c]:
                j += 1
            elif (c == 39 or c == 45) and j + 1 < n and WORD[line[j + 1]]:
                j += 2
            else:
                break
        out.append(line[i:j])
        i = j
    return out


def term(tok):
    t = tok.replace(b"'", b"")
    t = t.lower()
    if t.isdigit():
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


def usage_error():
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        usage_error()
    a = args[0]
    if not re.fullmatch(r"[0-9]+", a):
        usage_error()
    s = a.lstrip("0")
    if len(s) > 4:
        usage_error()
    K = int(s) if s else 0
    if not (1 <= K <= 1000):
        usage_error()

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
    df = {}
    total = {}
    for d in docs:
        c = {}
        for line in d:
            for tok in tokens(line):
                t = term(tok)
                if t is not None:
                    c[t] = c.get(t, 0) + 1
        doc_counts.append(c)
        for t, v in c.items():
            df[t] = df.get(t, 0) + 1
            total[t] = total.get(t, 0) + v

    out = bytearray()
    for idx, c in enumerate(doc_counts, 1):
        items = []
        for t, tf in c.items():
            sc = tf * 1000 * (N + 1) // (df[t] * (tf + 2))
            items.append((-sc, t))
        items.sort()
        out += b"doc %d:" % idx
        for negsc, t in items[:K]:
            out += b" " + t + b"=" + str(-negsc).encode()
        out += b"\n"

    items = sorted((-v, t) for t, v in total.items())
    out += b"all:"
    for negv, t in items[:K]:
        out += b" " + t + b"=" + str(-negv).encode()
    out += b"\n"

    sys.stdout.buffer.write(bytes(out))
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
