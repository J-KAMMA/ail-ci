from ail.types import BigInt


def takes_int(x: int) -> int:
    return x + 1


big: BigInt = 2 ** 100
try:
    print(takes_int(big))
except OverflowError as exc:
    print("OverflowError:", exc)
