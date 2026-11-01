import operator


def main() -> int:
    checks = {
        "eq": operator.eq,
        "ne": operator.ne,
        "lt": operator.lt,
        "le": operator.le,
        "gt": operator.gt,
        "ge": operator.ge,
    }
    pairs = [(3, 5), (5, 3), (4, 4)]
    for name in ("eq", "ne", "lt", "le", "gt", "ge"):
        check = checks[name]
        results = []
        for a, b in pairs:
            results.append(str(check(a, b)))
        print(name, " ".join(results))
    print("sorted", sorted(pairs, key=operator.itemgetter(1)))
    print("negated", [operator.neg(n) for n in (3, -1, 0)])
    print("not", operator.not_(0), operator.not_(2))
    return 0


main()
