import sys


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def next_prime(n: int) -> int:
    c = n + 1
    if c <= 2:
        return 2
    if c % 2 == 0:
        c += 1
    while not is_prime(c):
        c += 2
    return c


def prev_prime(n: int) -> int | None:
    c = n - 1
    while c >= 2:
        if is_prime(c):
            return c
        c -= 1
    return None


def main() -> None:
    n = int(sys.stdin.readline().strip())
    status = "prime" if is_prime(n) else "not prime"
    nxt = next_prime(n)
    prv = prev_prime(n)
    print(f"{status} {nxt} {prv if prv is not None else 'none'}")


if __name__ == "__main__":
    main()
