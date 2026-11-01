import functools
import operator


def main() -> int:
    values = [1, 2, 3, 4, 5]
    print("sum", functools.reduce(operator.add, values))
    print("product", functools.reduce(operator.mul, values))
    print("negated", list(map(operator.neg, values)))
    print("doubled", list(map(operator.add, values, values)))
    print("absolute", list(map(operator.abs, [-3, 4, -5])))
    rows = [("a", 3), ("b", 1), ("c", 2)]
    print("rows", sorted(rows, key=operator.itemgetter(1)))
    names = ["pear", "fig", "apple"]
    print("names", sorted(names, key=operator.itemgetter(0)))
    print("max", functools.reduce(lambda x, y: x if operator.ge(x, y) else y, values))
    return 0


main()
