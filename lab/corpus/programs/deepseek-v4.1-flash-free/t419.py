from decimal import Decimal, getcontext
import sys

getcontext().prec = 28

QUANT = Decimal("0.0000000001")


def main() -> None:
    data = sys.stdin.read().split()
    numbers = [int(tok) for tok in data]

    inverses = [Decimal(1) / Decimal(n) for n in numbers if n != 0]

    total = Decimal(0)
    product = Decimal(1)
    for inv in inverses:
        total += inv
        product *= inv

    print(total.quantize(QUANT))
    print(product.quantize(QUANT))


if __name__ == "__main__":
    main()
