import sys


def build_stop():
    s = set()
    words = (
        "an and are as at be but by for from had has have he her his in into is it "
        "its not of on or our she so than that the their them then there these they "
        "this to was we were which will with you your"
    )
    for w in words.split():
        s.add(w.encode())
    return s


STOP = build_stop()


def build_word():
    b = bytearray(256)
    for i in range(48, 58):
        b[i] = 1
    for i in range(65, 91):
        b[i] = 1
    for i in range(97, 123):
        b[i] = 1
    for i in range(128, 256):
        b[i] = 1
    return bytes(b)


WORD = build_word()


def emit(tok, out):
    cleaned = bytearray()
    i = 0
    while i < len(tok):
        c = tok[i]
        if c != 39:
            if 65 <= c <= 90:
                c = c + 32
            cleaned.append(c)
        i += 1
    tok = bytes(cleaned)
    n = len(tok)
    if n == 0:
        return
    alldig = True
    i = 0
    while i < n:
        if tok[i] < 48 or tok[i] > 57:
            alldig = False
            break
        i += 1
    if alldig:
        tok = b"#" + str(n).encode()
        n = len(tok)
    if n < 2:
        return
    if tok in STOP:
        return
    if n >= 5 and tok.endswith(b"ing"):
        tok = tok[0:n - 3]
    elif n >= 4 and tok.endswith(b"s") and not tok.endswith(b"ss"):
        tok = tok[0:n - 1]
    out.append(tok)


def terms_of_line(line, out):
    n = len(line)
    i = 0
    while i < n:
        if WORD[line[i]] == 0:
            i += 1
            continue
        start = i
        j = i + 1
        while j < n:
            b = line[j]
            if WORD[b] != 0:
                j += 1
            elif (b == 39 or b == 45) and j + 1 < n and WORD[line[j + 1]] != 0:
                j += 2
            else:
                break
        emit(line[start:j], out)
        i = j
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    arg = sys.argv[1]
    if len(arg) == 0:
        sys.exit(1)
    k = 0
    ok = True
    for ch in arg:
        if ch < "0" or ch > "9":
            ok = False
            break
        if k <= 1000:
            k = k * 10 + ord(ch) - 48
    if not ok:
        sys.exit(1)
    if k < 1 or k > 1000:
        sys.exit(1)

    data = sys.stdin.buffer.read()
    if len(data) == 0:
        lines = []
    else:
        lines = data.split(b"\n")
        if data.endswith(b"\n"):
            lines.pop()

    docs = []
    cur = []
    for ln in lines:
        if ln == b"%%" or ln == b"%%\r":
            docs.append(cur)
            cur = []
        else:
            cur.append(ln)
    docs.append(cur)

    ndocs = len(docs)
    df = {}
    total = {}
    doc_counts = []
    for dl in docs:
        cnt = {}
        for ln in dl:
            found = []
            terms_of_line(ln, found)
            for t in found:
                if t in cnt:
                    cnt[t] = cnt[t] + 1
                else:
                    cnt[t] = 1
        doc_counts.append(cnt)
        for t in cnt:
            c = cnt[t]
            if t in df:
                df[t] = df[t] + 1
            else:
                df[t] = 1
            if t in total:
                total[t] = total[t] + c
            else:
                total[t] = c

    n1 = ndocs + 1
    out = []
    d = 0
    while d < ndocs:
        cnt = doc_counts[d]
        items = []
        for t in cnt:
            tf = cnt[t]
            dfv = df[t]
            score = (tf * 1000 * n1) // (dfv * (tf + 2))
            items.append((t, score))
        items.sort(key=lambda p: (-p[1], p[0]))
        lim = k
        if len(items) < lim:
            lim = len(items)
        parts = [b"doc ", str(d + 1).encode(), b":"]
        x = 0
        while x < lim:
            parts.append(b" ")
            parts.append(items[x][0])
            parts.append(b"=")
            parts.append(str(items[x][1]).encode())
            x += 1
        parts.append(b"\n")
        out.append(b"".join(parts))
        d += 1

    items2 = []
    for t in total:
        items2.append((t, total[t]))
    items2.sort(key=lambda p: (-p[1], p[0]))
    lim = k
    if len(items2) < lim:
        lim = len(items2)
    parts = [b"all:"]
    x = 0
    while x < lim:
        parts.append(b" ")
        parts.append(items2[x][0])
        parts.append(b"=")
        parts.append(str(items2[x][1]).encode())
        x += 1
    parts.append(b"\n")
    out.append(b"".join(parts))

    sys.stdout.buffer.write(b"".join(out))


main()
