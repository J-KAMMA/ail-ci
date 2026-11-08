"""Dataframe-like groupby / sum / filter over lists of rows (parallel integer columns)."""


class Frame:
    def __init__(self, key: list[int], a: list[int], b: list[int]) -> None:
        self.key = key
        self.a = a
        self.b = b

    def rows(self) -> int:
        return len(self.key)


def total_of(xs: list[int]) -> int:
    acc = 0
    for x in xs:
        acc += x
    return acc


def group_sum(key: list[int], vals: list[int], ngroups: int) -> list[int]:
    out = [0] * ngroups
    i = 0
    n = len(key)
    while i < n:
        out[key[i]] += vals[i]
        i += 1
    return out


def group_count(key: list[int], ngroups: int) -> list[int]:
    out = [0] * ngroups
    for k in key:
        out[k] += 1
    return out


def filter_sum(vals: list[int], lo: int, hi: int) -> int:
    acc = 0
    for v in vals:
        if v >= lo and v < hi:
            acc += v
    return acc


def weighted_sum(a: list[int], b: list[int], w: int) -> int:
    acc = 0
    i = 0
    n = len(a)
    while i < n:
        acc += a[i] * w + b[i]
        i += 1
    return acc


def max_group_count(counts: list[int]) -> int:
    best = 0
    for c in counts:
        if c > best:
            best = c
    return best


def scaled_total(vals: list[int], num: int, den: int) -> int:
    acc = 0
    for v in vals:
        acc += v * num // den
    return acc
