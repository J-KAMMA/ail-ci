from fractions import Fraction


def mean(xs):
    if not xs:
        return None
    total = Fraction(0)
    for x in xs:
        total = total + x
    return total / len(xs)


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    mid = len(s) // 2
    if len(s) % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def variance(xs):
    m = mean(xs)
    if m is None:
        return None
    total = Fraction(0)
    for x in xs:
        d = x - m
        total = total + d * d
    return total / len(xs)


def main():
    data = [Fraction(1, 2), Fraction(3, 4), Fraction(3, 4), Fraction(1, 4), Fraction(5, 4)]
    print(mean(data), median(data), variance(data))
    print(float(mean(data)), float(median(data)), float(variance(data)))
    print(mean([Fraction(1, 3)]), median([Fraction(1, 3)]), variance([Fraction(1, 3)]))
    for empty in [[], []]:
        print(mean(empty), median(empty), variance(empty))
    counts = {}
    for x in data:
        counts[x] = counts.get(x, 0) + 1
    best = max(counts.values())
    print(sorted(k for k in counts if counts[k] == best))


main()
