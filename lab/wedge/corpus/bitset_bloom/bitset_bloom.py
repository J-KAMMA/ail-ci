"""Bit-set / bloom filter: membership tests over integer hashes."""


def make_hashes(n: int, seed: int, mod: int) -> list[int]:
    out = []
    state = seed
    i = 0
    while i < n:
        state = (state * 6364136223846793005 + 1442695040888963407) % 9223372036854775807
        out.append(state % mod)
        i += 1
    return out


def bloom_set(keys: list[int], bits: int) -> list[int]:
    table = [0] * bits
    for k in keys:
        a = k % bits
        b = (k // 7 + 13) % bits
        c = (k // 131 + 7) % bits
        table[a] = 1
        table[b] = 1
        table[c] = 1
    return table


def bloom_probe(table: list[int], keys: list[int], bits: int) -> int:
    hits = 0
    for k in keys:
        a = k % bits
        b = (k // 7 + 13) % bits
        c = (k // 131 + 7) % bits
        if table[a] == 1 and table[b] == 1 and table[c] == 1:
            hits += 1
    return hits


def popcount(table: list[int]) -> int:
    n = 0
    for v in table:
        n += v
    return n


def set_intersect(a: list[int], b: list[int]) -> int:
    n = 0
    i = 0
    while i < len(a):
        if a[i] == 1 and b[i] == 1:
            n += 1
        i += 1
    return n


def rotate_xor(keys: list[int]) -> int:
    acc = 0
    for k in keys:
        acc ^= (k << 7) & 0xFFFFFFFF
        acc = (acc + k) & 0xFFFFFFFF
    return acc


def multiples(keys: list[int], d: int) -> int:
    n = 0
    for k in keys:
        if k % d == 0:
            n += 1
    return n
