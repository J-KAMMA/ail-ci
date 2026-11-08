"""Numeric loops over lists of floats."""


def dot(a: list[float], b: list[float]) -> float:
    acc = 0.0
    i = 0
    n = len(a)
    while i < n:
        acc += a[i] * b[i]
        i += 1
    return acc


def mean(xs: list[float]) -> float:
    acc = 0.0
    for x in xs:
        acc += x
    return acc / len(xs)


def variance(xs: list[float]) -> float:
    m = mean(xs)
    acc = 0.0
    for x in xs:
        d = x - m
        acc += d * d
    return acc / len(xs)


def norm(xs: list[float]) -> float:
    acc = 0.0
    for x in xs:
        acc += x * x
    return acc ** 0.5


def scale_into(xs: list[float], k: float) -> list[float]:
    out = []
    for x in xs:
        out.append(x * k)
    return out


def max_abs(xs: list[float]) -> float:
    best = 0.0
    for x in xs:
        v = x if x >= 0.0 else -x
        if v > best:
            best = v
    return best


def sq_sum(xs: list[float]) -> float:
    acc = 0.0
    for x in xs:
        acc += x * x
    return acc


def blend(a: list[float], b: list[float], w: float) -> float:
    acc = 0.0
    i = 0
    n = len(a)
    while i < n:
        acc += a[i] * w + b[i] * (1.0 - w)
        i += 1
    return acc
