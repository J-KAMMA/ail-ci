import sys
from collections import Counter

STOP_WORDS = {
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by", b"for",
    b"from", b"had", b"has", b"have", b"he", b"her", b"his", b"in",
    b"into", b"is", b"it", b"its", b"not", b"of", b"on", b"or", b"our",
    b"she", b"so", b"than", b"that", b"the", b"their", b"them", b"then",
    b"there", b"these", b"they", b"this", b"to", b"was", b"we", b"were",
    b"which", b"will", b"with", b"you", b"your",
}


def is_word_byte(b):
    return (
        48 <= b <= 57
        or 65 <= b <= 90
        or 97 <= b <= 122
        or b >= 128
    )


def make_term(raw):
    token = raw.replace(b"'", b"")
    token = token.lower()

    if token and all(48 <= b <= 57 for b in token):
        token = b"#" + str(len(token)).encode()

    if len(token) < 2:
        return None

    if token in STOP_WORDS:
        return None

    if len(token) >= 5 and token.endswith(b"ing"):
        token = token[:-3]
    elif len(token) >= 4 and token.endswith(b"s") and not token.endswith(b"ss"):
        token = token[:-1]

    return token


def extract_terms(line):
    terms = []
    i = 0
    n = len(line)

    while i < n:
        if not is_word_byte(line[i]):
            i += 1
            continue

        start = i
        i += 1

        while i < n:
            b = line[i]

            if is_word_byte(b):
                i += 1
            elif b == 0x27 or b == 0x2D:
                if i + 1 < n and is_word_byte(line[i + 1]):
                    i += 1
                else:
                    break
            else:
                break

        term = make_term(line[start:i])
        if term is not None:
            terms.append(term)

    return terms


def parse_k(argv):
    if len(argv) != 2:
        return None

    arg = argv[1]
    if not arg or not all('0' <= c <= '9' for c in arg):
        return None

    normalized = arg.lstrip('0')
    if not normalized or len(normalized) > 4:
        return None

    k = int(normalized)
    if k < 1 or k > 1000:
        return None

    return k


def main():
    k = parse_k(sys.argv)
    if k is None:
        return 1

    data = sys.stdin.buffer.read()

    if not data:
        lines = []
    else:
        lines = data.split(b"\n")
        if data.endswith(b"\n"):
            lines.pop()

    documents = [[]]

    for line in lines:
        if line == b"%%" or line == b"%%\r":
            documents.append([])
        else:
            documents[-1].append(line)

    doc_counters = []
    total_counts = Counter()

    for doc_lines in documents:
        counter = Counter()

        for line in doc_lines:
            for term in extract_terms(line):
                counter[term] += 1
                total_counts[term] += 1

        doc_counters.append(counter)

    df = Counter()
    for counter in doc_counters:
        for term in counter:
            df[term] += 1

    n_docs = len(doc_counters)
    output = []

    for doc_number, counter in enumerate(doc_counters, 1):
        scored = []

        for term, tf in counter.items():
            score = tf * 1000 * (n_docs + 1) // (df[term] * (tf + 2))
            scored.append((term, score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        scored = scored[:k]

        parts = [b"doc " + str(doc_number).encode() + b":"]
        for term, score in scored:
            parts.append(b" " + term + b"=" + str(score).encode())

        output.append(b"".join(parts))

    overall = sorted(total_counts.items(), key=lambda item: (-item[1], item[0]))
    overall = overall[:k]

    parts = [b"all:"]
    for term, count in overall:
        parts.append(b" " + term + b"=" + str(count).encode())

    output.append(b"".join(parts))

    sys.stdout.buffer.write(b"\n".join(output) + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
