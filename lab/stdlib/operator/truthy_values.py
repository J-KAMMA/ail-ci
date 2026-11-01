import operator


def check(label: str, value) -> None:
    print(label, operator.truth(value), operator.not_(value))


def main() -> int:
    check("empty list", [])
    check("one item", [1])
    check("zero", 0)
    check("one", 1)
    check("empty str", "")
    check("text", "x")
    check("none", None)
    check("empty dict", {})
    check("float zero", 0.0)
    check("float", 0.5)
    marker = None
    print(operator.is_(marker, None), operator.is_not(marker, None))
    first = [1, 2]
    same = first
    other = [1, 2]
    print(operator.is_(first, same), operator.is_(first, other))
    print(operator.is_not(first, same), operator.is_not(first, other))
    print(operator.truth(operator.and_(0, 5)), operator.truth(operator.or_(0, 5)))
    return 0


main()
