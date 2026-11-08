"""Ranking: count terms, sort by count, take a top-k slice (term_rank-like)."""


def count_terms(words: list[str], vocab_size: int) -> list[int]:
    counts = [0] * vocab_size
    for w in words:
        idx = 0
        h = 0
        for ch in w:
            h = (h * 31 + ord(ch)) % vocab_size
            idx = h
        counts[idx] += 1
    return counts


def top_indices(counts: list[int], k: int) -> list[int]:
    order = []
    i = 0
    while i < len(counts):
        order.append(i)
        i += 1
    j = 1
    while j < len(order):
        cur = order[j]
        cv = counts[cur]
        p = j - 1
        while p >= 0 and counts[order[p]] < cv:
            order[p + 1] = order[p]
            p -= 1
        order[p + 1] = cur
        j += 1
    return order[:k]


def count_above(counts: list[int], threshold: int) -> int:
    n = 0
    for c in counts:
        if c >= threshold:
            n += 1
    return n


def total_count(counts: list[int]) -> int:
    n = 0
    for c in counts:
        n += c
    return n


def max_count(counts: list[int]) -> int:
    best = 0
    for c in counts:
        if c > best:
            best = c
    return best


def top_score(counts: list[int], k: int) -> int:
    idx = top_indices(counts, k)
    total = 0
    for i in idx:
        total += counts[i]
    return total


def hash_spread(words: list[str], vocab_size: int, buckets: int) -> int:
    seen = [0] * buckets
    for w in words:
        h = 0
        for ch in w:
            h = (h * 131 + ord(ch)) % vocab_size
        seen[h % buckets] += 1
    used = 0
    for s in seen:
        if s > 0:
            used += 1
    return used
