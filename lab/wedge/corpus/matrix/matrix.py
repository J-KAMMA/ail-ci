"""Dense matrix operations over flat integer lists (numpy-like payload)."""


def mat_mul(a: list[int], b: list[int], n: int) -> list[int]:
    out = [0] * (n * n)
    i = 0
    while i < n:
        j = 0
        while j < n:
            acc = 0
            k = 0
            while k < n:
                acc += a[i * n + k] * b[k * n + j]
                k += 1
            out[i * n + j] = acc
            j += 1
        i += 1
    return out


def trace(m: list[int], n: int) -> int:
    acc = 0
    i = 0
    while i < n:
        acc += m[i * n + i]
        i += 1
    return acc


def row_sums(m: list[int], n: int) -> list[int]:
    out = []
    i = 0
    while i < n:
        acc = 0
        j = 0
        while j < n:
            acc += m[i * n + j]
            j += 1
        out.append(acc)
        i += 1
    return out


def max_element(m: list[int]) -> int:
    best = 0
    first = 1
    for v in m:
        if first == 1 or v > best:
            best = v
            first = 0
    return best


def apply_threshold(m: list[int], t: int) -> int:
    n = 0
    for v in m:
        if v > t:
            v = t
        n += v
    return n


def scale_vec(v: list[int], k: int) -> int:
    acc = 0
    for x in v:
        acc += x * k
    return acc


def count_negative(m: list[int]) -> int:
    n = 0
    for v in m:
        if v < 0:
            n += 1
    return n


def identity(n: int) -> list[int]:
    out = [0] * (n * n)
    i = 0
    while i < n:
        out[i * n + i] = 1
        i += 1
    return out
