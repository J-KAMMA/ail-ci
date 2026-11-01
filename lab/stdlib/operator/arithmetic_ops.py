import functools
import operator


def apply_all(a: int, b: int) -> None:
    print("add", operator.add(a, b))
    print("sub", operator.sub(a, b))
    print("mul", operator.mul(a, b))
    print("truediv", operator.truediv(a, b))
    print("floordiv", operator.floordiv(a, b))
    print("mod", operator.mod(a, b))
    print("pow", operator.pow(a, 2))
    print("and", operator.and_(a, b))
    print("or", operator.or_(a, b))
    print("xor", operator.xor(a, b))


def main() -> int:
    apply_all(17, 5)
    print("neg", operator.neg(9), "pos", operator.pos(-4), "abs", operator.abs(-11))
    print("invert", operator.invert(5))
    print("shift", operator.lshift(3, 4), operator.rshift(96, 3))
    values = [2, 3, 4]
    print("sum", functools.reduce(operator.add, values))
    print("product", functools.reduce(operator.mul, values))
    biggest = functools.reduce(lambda x, y: x if operator.gt(x, y) else y, values)
    print("biggest", biggest)
    return 0


main()
