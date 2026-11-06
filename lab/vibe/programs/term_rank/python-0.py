import sys

STOP_WORDS = frozenset(b"an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your".split())

LOWER = bytes.maketrans(bytes(range(65, 91)), bytes(range(97, 123)))
QUOTE = 0x27
HYPHEN = 0x2D


def is_word_byte(b):
    return 48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122 or b >= 128


def line_terms(line):
    n = len(line)
    result = []
    i = 0
    while i < n:
        if not is_word_byte(line[i]):
            i += 1
            continue
        j = i + 1
        while j < n:
            c = line[j]
            if is_word_byte(c):
                j += 1
            elif c == QUOTE or c == HYPHEN:
                if j + 1 < n and is_word_byte(line[j - 1]) and is_word_byte(line[j + 1]):
                    j += 1
                else:
                    break
            else:
                break
        raw = line[i:j]
        i = j

        t = raw.replace(b"'", b"").translate(LOWER)
        if t.isdigit():
            t = b"#" + str(len(t)).encode()
        if len(t) < 2:
            continue
        if t in STOP_WORDS:
            continue
        if len(t) >= 5 and t.endswith(b"ing"):
            t = t[:-3]
        elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
            t = t[:-1]
        result.append(t)
    return result


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        return 1
    s = args[0]
    if not s or any(ch < "0" or ch > "9" for ch in s):
        return 1
    k = int(s)
    if k < 1 or k > 1000:
        return 1

    data = sys.stdin.buffer.read()
    if not data:
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

    doc_counts = []
    for doc in docs:
        counts = {}
        for line in doc:
            for term in line_terms(line):
                counts[term] = counts.get(term, 0) + 1
        doc_counts.append(counts)

    n_docs = len(doc_counts)
    df = {}
    total = {}
    for counts in doc_counts:
        for term, c in counts.items():
            df[term] = df.get(term, 0) + 1
            total[term] = total.get(term, 0) + c

    out = sys.stdout.buffer

    for idx, counts in enumerate(doc_counts, 1):
        scored = []
        for term, tf in counts.items():
            score = tf * 1000 * (n_docs + 1) // (df[term] * (tf + 2))
            scored.append((score, term))
        scored.sort(key=lambda x: (-x[0], x[1]))
        if len(scored) > k:
            scored = scored[:k]
        parts = [term + b"=" + str(score).encode() for score, term in scored]
        head = b"doc " + str(idx).encode() + b":"
        if parts:
            out.write(head + b" " + b" ".join(parts) + b"\n")
        else:
            out.write(head + b"\n")

    ranked = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) > k:
        ranked = ranked[:k]
    parts = [term + b"=" + str(c).encode() for term, c in ranked]
    if parts:
        out.write(b"all: " + b" ".join(parts) + b"\n")
    else:
        out.write(b"all:\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
