import re
import sys

TOKEN_RE = re.compile(rb"[A-Za-z0-9\x80-\xff]+(?:['-][A-Za-z0-9\x80-\xff]+)*")
LOWER = bytes.maketrans(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    b"abcdefghijklmnopqrstuvwxyz",
)
STOP_WORDS = set(
    b"an and are as at be but by for from had has have he her his in into is it its "
    b"not of on or our she so than that the their them then there these they this to "
    b"was we were which will with you your".split()
)


def parse_k():
    if len(sys.argv) != 2:
        sys.exit(1)

    s = sys.argv[1]
    if not s or any(c < "0" or c > "9" for c in s):
        sys.exit(1)

    digits = s.lstrip("0")
    if not digits or len(digits) > 4:
        sys.exit(1)

    value = int(digits)
    if value < 1 or value > 1000:
        sys.exit(1)

    return value


def make_term(raw):
    term = raw.replace(b"'", b"").translate(LOWER)

    if term.isdigit():
        term = b"#" + str(len(term)).encode("ascii")

    if len(term) < 2:
        return None

    if term in STOP_WORDS:
        return None

    if len(term) >= 5 and term.endswith(b"ing"):
        term = term[:-3]
    elif len(term) >= 4 and term.endswith(b"s") and not term.endswith(b"ss"):
        term = term[:-1]

    return term


def main():
    k = parse_k()
    data = sys.stdin.buffer.read()

    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()

    documents = []
    current = {}

    for line in lines:
        if line == b"%%" or line == b"%%\r":
            documents.append(current)
            current = {}
            continue

        for match in TOKEN_RE.finditer(line):
            term = make_term(match.group(0))
            if term is not None:
                current[term] = current.get(term, 0) + 1

    documents.append(current)

    n = len(documents)
    df = {}
    totals = {}

    for counts in documents:
        for term, tf in counts.items():
            df[term] = df.get(term, 0) + 1
            totals[term] = totals.get(term, 0) + tf

    output = []

    for index, counts in enumerate(documents, 1):
        ranked = []
        for term, tf in counts.items():
            score = tf * 1000 * (n + 1) // (df[term] * (tf + 2))
            ranked.append((term, score))

        ranked.sort(key=lambda item: (-item[1], item[0]))
        ranked = ranked[:k]

        line = b"doc " + str(index).encode("ascii") + b":"
        if ranked:
            line += b" " + b" ".join(
                term + b"=" + str(score).encode("ascii")
                for term, score in ranked
            )
        output.append(line)

    ranked_all = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:k]

    line = b"all:"
    if ranked_all:
        line += b" " + b" ".join(
            term + b"=" + str(count).encode("ascii")
            for term, count in ranked_all
        )
    output.append(line)

    sys.stdout.buffer.write(b"\n".join(output) + b"\n")


if __name__ == "__main__":
    main()
