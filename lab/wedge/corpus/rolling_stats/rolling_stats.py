"""Rolling statistics over integer samples: windowed sums, runs, streaks."""

WINDOW = 64


def make_samples(n: int, seed: int) -> list[int]:
    out = []
    i = 0
    state = seed
    while i < n:
        state = (state * 1103515245 + 12345) % 2147483648
        out.append(state % 1000)
        i += 1
    return out


def window_sums(xs: list[int], w: int) -> list[int]:
    out = []
    acc = 0
    i = 0
    n = len(xs)
    while i < n:
        acc += xs[i]
        if i >= w:
            acc -= xs[i - w]
        if i >= w - 1:
            out.append(acc)
        i += 1
    return out


def longest_run(xs: list[int], want: int) -> int:
    best = 0
    cur = 0
    for x in xs:
        if x == want:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def rising_streak(xs: list[int]) -> int:
    best = 0
    cur = 1
    i = 1
    n = len(xs)
    while i < n:
        if xs[i] > xs[i - 1]:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 1
        i += 1
    if n > 0 and best == 0:
        best = 1
    return best


def count_over(xs: list[int], limit: int) -> int:
    n = 0
    for x in xs:
        if x > limit:
            n += 1
    return n


def mean_scaled(xs: list[int], scale: int) -> int:
    acc = 0
    for x in xs:
        acc += x * scale
    return acc // len(xs)


def second_moment(xs: list[int]) -> int:
    acc = 0
    for x in xs:
        acc += x * x
    return acc


def total(xs: list[int]) -> int:
    acc = 0
    for x in xs:
        acc += x
    return acc
