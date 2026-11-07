import sys

STOP_WORDS: set[bytes] = {
    b"an", b"and", b"are", b"as", b"at", b"be", b"but", b"by",
    b"for", b"from", b"had", b"has", b"have", b"he", b"her", b"his",
    b"in", b"into", b"is", b"it", b"its", b"not", b"of", b"on",
    b"or", b"our", b"she", b"so", b"than", b"that", b"the", b"their",
    b"them", b"then", b"there", b"these", b"they", b"this", b"to",
    b"was", b"we", b"were", b"which", b"will", b"with", b"you", b"your"
}


def is_word(c: int) -> bool:
    if c >= 48 and c <= 57:
        return True
    if c >= 65 and c <= 90:
        return True
    if c >= 97 and c <= 122:
        return True
    return c >= 128


def is_joiner(c: int) -> bool:
    return c == 39 or c == 45


def is_separator(line: bytes) -> bool:
    return line == b"%%" or line == b"%%\r"


def transform(raw: bytes) -> bytes:
    t: bytes = raw.replace(b"'", b"")
    t = t.lower()

    all_digits: bool = len(t) > 0
    j: int = 0
    while j < len(t):
        c: int = t[j]
        if c < 48 or c > 57:
            all_digits = False
            break
        j += 1

    if all_digits:
        t = b"#" + str(len(t)).encode()

    if len(t) < 2:
        return b""
    if t in STOP_WORDS:
        return b""

    if len(t) >= 5 and t.endswith(b"ing"):
        t = t[:-3]
    elif len(t) >= 4 and t.endswith(b"s") and not t.endswith(b"ss"):
        t = t[:-1]

    return t


def scan_line(line: bytes, counts: dict[bytes, int]) -> None:
    i: int = 0
    n: int = len(line)

    while i < n:
        c: int = line[i]
        if is_word(c):
            start: int = i
            i += 1

            while i < n:
                c2: int = line[i]
                if is_word(c2):
                    i += 1
                elif is_joiner(c2) and i + 1 < n and is_word(line[i + 1]):
                    i += 1
                else:
                    break

            raw: bytes = line[start:i]
            term: bytes = transform(raw)

            if len(term) > 0:
                if term in counts:
                    counts[term] = counts[term] + 1
                else:
                    counts[term] = 1
        else:
            i += 1


def finalize_stats(counts: dict[bytes, int], df: dict[bytes, int], totals: dict[bytes, int]) -> None:
    for term in counts:
        tf: int = counts[term]

        if term in df:
            df[term] = df[term] + 1
        else:
            df[term] = 1

        if term in totals:
            totals[term] = totals[term] + tf
        else:
            totals[term] = tf


def term_key(item: tuple[int, bytes]) -> bytes:
    return item[1]


def number_key(item: tuple[int, bytes]) -> int:
    return item[0]


def top_terms(counts: dict[bytes, int], k: int, df: dict[bytes, int], n_docs: int) -> list[tuple[int, bytes]]:
    items: list[tuple[int, bytes]] = []

    for term in counts:
        tf: int = counts[term]
        d: int = df[term]
        score: int = (tf * 1000 * (n_docs + 1)) // (d * (tf + 2))
        items.append((score, term))

    items.sort(key=term_key)
    items.sort(key=number_key, reverse=True)
    return items[:k]


def make_doc_line(num: int, items: list[tuple[int, bytes]]) -> bytes:
    parts: list[bytes] = []
    parts.append(b"doc " + str(num).encode() + b":")

    for item in items:
        parts.append(b" " + item[1] + b"=" + str(item[0]).encode())

    return b"".join(parts)


def write_doc(num: int, counts: dict[bytes, int], k: int, df: dict[bytes, int], n_docs: int) -> None:
    items: list[tuple[int, bytes]] = top_terms(counts, k, df, n_docs)
    line: bytes = make_doc_line(num, items)
    sys.stdout.buffer.write(line + b"\n")


def make_all_line(totals: dict[bytes, int], k: int) -> bytes:
    items: list[tuple[int, bytes]] = []

    for term in totals:
        items.append((totals[term], term))

    items.sort(key=term_key)
    items.sort(key=number_key, reverse=True)

    parts: list[bytes] = [b"all:"]
    for item in items[:k]:
        parts.append(b" " + item[1] + b"=" + str(item[0]).encode())

    return b"".join(parts)


def write_all(totals: dict[bytes, int], k: int) -> None:
    line: bytes = make_all_line(totals, k)
    sys.stdout.buffer.write(line + b"\n")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(1)

    arg: str = sys.argv[1]
    k: int = 0
    ok: bool = True
    i: int = 0

    while i < len(arg):
        ch: str = arg[i]
        code: int = ord(ch)

        if code < 48 or code > 57:
            ok = False
            break

        if k <= 1000:
            k = k * 10 + (code - 48)
            if k > 1000:
                k = 1001

        i += 1

    if not ok or k < 1 or k > 1000:
        sys.exit(1)

    data: bytes = sys.stdin.buffer.read()
    lines: list[bytes] = data.split(b"\n")

    if len(lines) > 0 and len(lines[-1]) == 0:
        lines.pop()

    n_docs: int = 1
    for line in lines:
        if is_separator(line):
            n_docs += 1

    df: dict[bytes, int] = {}
    totals: dict[bytes, int] = {}
    counts: dict[bytes, int] = {}

    for line in lines:
        if is_separator(line):
            finalize_stats(counts, df, totals)
            counts.clear()
        else:
            scan_line(line, counts)

    finalize_stats(counts, df, totals)

    doc_counts: dict[bytes, int] = {}
    doc_num: int = 1

    for line in lines:
        if is_separator(line):
            write_doc(doc_num, doc_counts, k, df, n_docs)
            doc_num += 1
            doc_counts.clear()
        else:
            scan_line(line, doc_counts)

    write_doc(doc_num, doc_counts, k, df, n_docs)
    write_all(totals, k)


main()
