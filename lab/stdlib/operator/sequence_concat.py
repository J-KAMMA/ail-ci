import operator


def join_all(parts):
    out = []
    for part in parts:
        out = operator.iadd(out, part)
    return out


def main() -> int:
    left = [1, 2, 3]
    right = [4, 5]
    print(operator.concat(left, right))
    print(operator.concat("abc", "def"))
    print(operator.length_hint(left))
    print(operator.index(7))
    acc = []
    for part in (["a"], ["b", "c"], ["d"]):
        acc = operator.iadd(acc, part)
    print(acc)
    return 0


main()
