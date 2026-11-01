import operator


def main() -> int:
    flags = 0
    flags = operator.or_(flags, 1)
    flags = operator.or_(flags, 4)
    flags = operator.xor(flags, 1)
    print(flags)
    print(operator.and_(flags, 4) != 0)
    print(operator.lshift(1, 6), operator.rshift(64, 3))
    print(operator.invert(0))
    for mask in (1, 2, 4, 8):
        print(mask, operator.truth(operator.and_(flags, mask)))
    combined = operator.or_(operator.lshift(1, 3), operator.lshift(1, 1))
    print("combined", combined)
    stripped = operator.and_(combined, operator.invert(operator.lshift(1, 1)))
    print("stripped", stripped)
    print("eq", operator.eq(stripped, 8), operator.ne(stripped, 8))
    print("truth", operator.truth(flags), operator.truth(combined))
    return 0


main()
