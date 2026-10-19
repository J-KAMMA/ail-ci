import sys


def sieve(limit: int) -> list[int]:
    """Return all primes less than or equal to limit using the Sieve of Eratosthenes."""
    if limit < 2:
        return []
    is_prime = [True] * (limit + 1)
    is_prime[0] = False
    is_prime[1] = False
    p = 2
    while p * p <= limit:
        if is_prime[p]:
            for multiple in range(p * p, limit + 1, p):
                is_prime[multiple] = False
        p += 1
    return [i for i, flag in enumerate(is_prime) if flag]


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    primes = sieve(10 * n)
    per_line = 15
    lines = [
        " ".join(str(p) for p in primes[i:i + per_line])
        for i in range(0, len(primes), per_line)
    ]
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
