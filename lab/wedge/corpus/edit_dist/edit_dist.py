"""Edit distance and fuzzy match over strings."""


def levenshtein(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = []
    i = 0
    while i <= m:
        prev.append(i)
        i += 1
    j = 1
    while j <= n:
        cur = [j]
        k = 1
        while k <= m:
            if a[j - 1] == b[k - 1]:
                cur.append(prev[k - 1])
            else:
                best = prev[k]
                if prev[k - 1] < best:
                    best = prev[k - 1]
                if cur[k - 1] < best:
                    best = cur[k - 1]
                cur.append(best + 1)
            k += 1
        prev = cur
        j += 1
    return prev[m]


def common_prefix(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    lim = n if n < m else m
    i = 0
    while i < lim and a[i] == b[i]:
        i += 1
    return i


def bigram_overlap(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    hits = 0
    i = 0
    while i + 1 < n:
        j = 0
        while j + 1 < m:
            if a[i] == b[j] and a[i + 1] == b[j + 1]:
                hits += 1
                break
            j += 1
        i += 1
    return hits


def hamming(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    lim = n if n < m else m
    d = 0
    i = 0
    while i < lim:
        if a[i] != b[i]:
            d += 1
        i += 1
    if n > m:
        d += n - m
    else:
        d += m - n
    return d


def best_match(word: str, cands: list) -> int:
    best = 0
    first = 1
    for c in cands:
        d = levenshtein(word, c)
        if first == 1 or d < best:
            best = d
            first = 0
    return best


def total_length(words: list) -> int:
    n = 0
    for w in words:
        n += len(w)
    return n
