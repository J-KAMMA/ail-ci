import sys
import heapq

STOP_WORDS = {
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by",
    b"for", b"from", b"had", b"has", b"have", b"he", b"her", b"his",
    b"in", b"into", b"is", b"it", b"its", b"not", b"of", b"on", b"or",
    b"our", b"she", b"so", b"than", b"that", b"the", b"their", b"them",
    b"then", b"there", b"these", b"they", b"this", b"to", b"was", b"we",
    b"were", b"which", b"will", b"with", b"you", b"your"
}


def is_word(c):
    return (48 <= c <= 57) or (65 <= c <= 90) or (97 <= c <= 122) or c >= 128


def is_joiner(c):
    return c == 39 or c == 45


def normalize(raw):
    t = raw.replace(b"'", b"").lower()

    if t.isdigit():
        t = b"#" + str(len(t)).encode()

    if len(t) < 2:
        return None

    if t in STOP_WORDS:
        return None

    if len(t) >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]

    return t


def terms_in_line(line):
    result = []
    n = len(line)
    i = 0

    while i < n:
        if is_word(line[i]):
            start = i
            j = i

            while j < n and is_word(line[j]):
                j += 1

            while j + 1 < n and is_joiner(line[j]) and is_word(line[j + 1]):
                j += 1
                while j < n and is_word(line[j]):
                    j += 1

            term = normalize(line[start:j])
            if term is not None:
                result.append(term)

            i = j
        else:
            i += 1

    return result


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    arg = sys.argv[1]

    if len(arg) == 0:
        sys.exit(1)

    for ch in arg:
        if ch < "0" or ch > "9":
            sys.exit(1)

    digits = arg.lstrip("0")

    if len(digits) == 0:
        sys.exit(1)

    if len(digits) > 4:
        sys.exit(1)

    k = int(digits)

    if k < 1 or k > 1000:
        sys.exit(1)

    data = sys.stdin.buffer.read()

    if len(data) == 0:
        lines = []
    else:
        lines = data.split(b"\n")
        if data.endswith(b"\n"):
            lines.pop()

    documents = []
    current = []

    for line in lines:
        if line == b"%%" or line == b"%%\r":
            documents.append(current)
            current = []
        else:
            current.append(line)

    documents.append(current)

    n_docs = len(documents)

    doc_counts = []
    all_counts = {}
    df = {}

    for doc_lines in documents:
        counts = {}

        for line in doc_lines:
            for term in terms_in_line(line):
                counts[term] = counts.get(term, 0) + 1

        doc_counts.append(counts)

        for term in counts:
            df[term] = df.get(term, 0) + 1
            all_counts[term] = all_counts.get(term, 0) + counts[term]

    output = []

    for d_index in range(n_docs):
        counts = doc_counts[d_index]
        ranked = []

        for term in counts:
            tf = counts[term]
            score = tf * 1000 * (n_docs + 1) // (df[term] * (tf + 2))
            ranked.append((-score, term))

        selected = heapq.nsmallest(k, ranked)

        output.append(b"doc " + str(d_index + 1).encode() + b":")

        for neg_score, term in selected:
            output.append(b" " + term + b"=" + str(-neg_score).encode())

        output.append(b"\n")

    ranked = []

    for term in all_counts:
        ranked.append((-all_counts[term], term))

    selected = heapq.nsmallest(k, ranked)

    output.append(b"all:")

    for neg_count, term in selected:
        output.append(b" " + term + b"=" + str(-neg_count).encode())

    output.append(b"\n")

    sys.stdout.buffer.write(b"".join(output))


if __name__ == "__main__":
    main()
