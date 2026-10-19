import sys
from typing import List


def is_prime(x: int) -> bool:
    if x < 2:
        return False
    if x < 4:
        return True
    if x % 2 == 0 or x % 3 == 0:
        return False
    i = 5
    while i * i <= x:
        if x % i == 0 or x % (i + 2) == 0:
            return False
        i += 6
    return True


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return
    n = int(data[0])
    values: List[int] = [int(tok) for tok in data[1:1 + n]]
    primes = [str(v) for v in values if is_prime(v)]
    if primes:
        print(" ".join(primes))
    else:
        print("none")


if __name__ == "__main__":
    main()
