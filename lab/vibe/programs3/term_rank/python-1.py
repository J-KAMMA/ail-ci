import sys
from collections import Counter


def is_word(b):
    return b >= 128 or 48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122


STOP_WORDS = frozenset(
    b"an and are as at be but by for from had has have he her his in into is it its "
    b"not of on or our she so than that the their them then there these they this to "
    b"was we were which will with you your".split()
)


def normalize(raw):
    if b"'" in raw:
        raw = raw.replace(b"'", b"")

    term = raw.lower()

    if term.isdigit():
        term = b"#" + str(len(term)).encode()

    if len(term) < 2:
        return None

    if term in STOP_WORDS:
        return None

    if len(term) >= 5 and term.endswith(b"ing"):
        term = term[:-3]
    elif len(term) >= 4 and term.endswith(b"s") and not term.endswith(b"ss"):
        term = term[:-1]

    return term


def iter_terms(line):
    n = len(line)
    i = 0

    while i < n:
        if not is_word(line[i]):
            i += 1
            continue

        start = i
        i += 1

        while i < n:
            c = line[i]

            if is_word(c):
                i += 1
            elif (c == 39 or c == 45) and i + 1 < n and is_word(line[i + 1]):
                i += 1
            else:
                break

        term = normalize(line[start:i])
        if term is not None:
            yield term


def main():
    args = sys.argv[1:]

    if len(args) != 1:
        return 1

    arg = args[0]

    if not arg or any(c < "0" or c > "9" for c in arg):
        return 1

    digits = arg.lstrip("0")

    if not digits or len(digits) > 4:
        return 1

    k = int(digits)

    if k < 1 or k > 1000:
        return 1

    docs = [Counter()]
    total = Counter()

    for line in sys.stdin.buffer:
        if line.endswith(b"\n"):
            line = line[:-1]

        if line == b"%%" or line == b"%%\r":
            docs.append(Counter())
            continue

        current = docs[-1]

        for term in iter_terms(line):
            current[term] += 1
            total[term] += 1

    n_docs = len(docs)
    df = Counter()

    for counts in docs:
        df.update(counts.keys())

    out = sys.stdout.buffer

    for d, counts in enumerate(docs, 1):
        scored = []

        for term, tf in counts.items():
            score = (tf * 1000 * (n_docs + 1)) // (df[term] * (tf + 2))
            scored.append((score, term))

        scored.sort(key=lambda item: (-item[0], item[1]))

        line = b"doc " + str(d).encode() + b":"

        if scored:
            chosen = scored[:k]
            line += b" " + b" ".join(
                term + b"=" + str(score).encode() for score, term in chosen
            )

        out.write(line + b"\n")

    overall = sorted(total.items(), key=lambda item: (-item[1], item[0]))[:k]
    line = b"all:"

    if overall:
        line += b" " + b" ".join(
            term + b"=" + str(count).encode() for term, count in overall
        )

    out.write(line + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
