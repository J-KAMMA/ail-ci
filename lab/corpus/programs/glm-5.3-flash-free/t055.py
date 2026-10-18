import sys


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def next_prime(n: int) -> int:
    candidate = max(n + 1, 2)
    while not is_prime(candidate):
        candidate += 1
    return candidate


def prev_prime(n: int) -> int | None:
    candidate = n - 1
    while candidate >= 2:
        if is_prime(candidate):
            return candidate
        candidate -= 1
    return None


def main() -> None:
    n = int(sys.stdin.readline())
    print("prime" if is_prime(n) else "not prime")
    print(next_prime(n))
    prev = prev_prime(n)
    print(prev if prev is not None else "none")


if __name__ == "__main__":
    main()
