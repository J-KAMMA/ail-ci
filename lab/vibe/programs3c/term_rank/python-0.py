import re
import sys
from collections import Counter

STOP = set(b"""an and are as at be but by for from had has have he her his in into is it its not of on or
our she so than that the their them then there these they this to was we were which will with
you your""".split())

WORD = [False] * 256
for _c in range(256):
    WORD[_c] = (48 <= _c <= 57) or (65 <= _c <= 90) or (97 <= _c <= 122) or _c >= 128


def tokens(line):
    n = len(line)
    out = []
    i = 0
    while i < n:
        if not WORD[line[i]]:
            i += 1
            continue
        start = i
        j = i
        while True:
            while j < n and WORD[line[j]]:
                j += 1
            if j + 1 < n and (line[j] == 39 or line[j] == 45) and WORD[line[j + 1]]:
                j += 1
            else:
                break
        out.append(line[start:j])
        i = j
    return out


def norm(tok):
    t = tok.replace(b"'", b"").lower()
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


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        sys.exit(1)
    arg = args[0]
    if not re.fullmatch(r"[0-9]+", arg):
        sys.exit(1)
    s = arg.lstrip("0")
    if s == "":
        sys.exit(1)
    if len(s) > 4:
        sys.exit(1)
    K = int(s)
    if K < 1 or K > 1000:
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
    for doc_lines in docs:
        c = Counter()
        for line in doc_lines:
            for tok in tokens(line):
                t = norm(tok)
                if t is not None:
                    c[t] += 1
        doc_counts.append(c)
        for t in c:
            df[t] += 1
        total.update(c)

    out_lines = []
    for d, c in enumerate(doc_counts, start=1):
        scored = []
        for t, tf in c.items():
            sc = (tf * 1000 * (N + 1)) // (df[t] * (tf + 2))
            scored.append((-sc, t))
        scored.sort()
        items = []
        for neg, t in scored[:K]:
            items.append(t + b"=" + str(-neg).encode())
        prefix = b"doc " + str(d).encode() + b":"
        out_lines.append(b" ".join([prefix] + items))

    ranked = sorted((-cnt, t) for t, cnt in total.items())
    items = []
    for neg, t in ranked[:K]:
        items.append(t + b"=" + str(-neg).encode())
    out_lines.append(b" ".join([b"all:"] + items))

    sys.stdout.buffer.write(b"\n".join(out_lines) + b"\n")
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
