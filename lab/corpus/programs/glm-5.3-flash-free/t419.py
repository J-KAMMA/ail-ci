import sys
from decimal import Decimal, getcontext


def main() -> None:
    getcontext().prec = 28
    numbers = [Decimal(token) for token in sys.stdin.read().split()]
    inverses = [Decimal(1) / n for n in numbers if n != 0]

    total = sum(inverses, Decimal(0))
    product = Decimal(1)
    for inverse in inverses:
        product *= inverse

    quantum = Decimal("0.0000000001")
    print(total.quantize(quantum))
    print(product.quantize(quantum))


if __name__ == "__main__":
    main()
