from fractions import Fraction


def main():
    vals = [Fraction(3, 4), Fraction(1, 2), Fraction(5, 6), Fraction(2, 2), Fraction(-1, 3), Fraction(1, 2)]
    print(sorted(vals))
    print(sorted(vals, reverse=True))
    print(min(vals), max(vals), sum(vals), sum(vals, Fraction(1, 10)))
    print(len(set(vals)), Fraction(1, 2) in vals, Fraction(7, 8) in vals)
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    for key in sorted(counts):
        print(key, counts[key])
    by_value = {Fraction(1, 2): "half", Fraction(2, 3): "two thirds"}
    print(by_value[Fraction(2, 4)], by_value.get(Fraction(3, 4), "missing"))
    print(hash(Fraction(1, 2)) == hash(Fraction(2, 4)))
    pairs = [(Fraction(2, 3), "b"), (Fraction(1, 3), "a"), (Fraction(2, 3), "c")]
    print(sorted(pairs))
    print(sorted(pairs, key=lambda p: p[0], reverse=True))
    print(list(map(str, vals)))
    print([v for v in vals if v > Fraction(1, 2)])


main()
