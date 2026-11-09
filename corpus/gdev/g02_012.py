# task: Compute the first 30 Fibonacci numbers using fast doubling and verify the identity F(2n) = F(n)(2F(n+1) − F(n)) for each n.
def fib_pair(n: int) -> tuple[int, int]:
    """Return (F(n), F(n+1)) using the fast doubling method."""
    if n == 0:
        return (0, 1)
    a, b = fib_pair(n >> 1)  # a = F(k), b = F(k+1) where k = n // 2
    c = a * (2 * b - a)      # F(2k)
    d = a * a + b * b        # F(2k+1)
    if n & 1:
        return (d, c + d)
    return (c, d)


def fib(n: int) -> int:
    """Return the n-th Fibonacci number F(n) using fast doubling."""
    return fib_pair(n)[0]


def fib_iterative(n: int) -> int:
    """Reference iterative Fibonacci used to cross-check fast doubling."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def main() -> None:
    count = 30
    all_identities_hold = True

    print("First 30 Fibonacci numbers (fast doubling):")
    for n in range(count):
        f_n, f_n1 = fib_pair(n)
        f_2n = fib(2 * n)

        if f_n != fib_iterative(n):
            raise AssertionError(f"Fast doubling mismatch at F({n})")

        identity_holds = f_2n == f_n * (2 * f_n1 - f_n)
        all_identities_hold = all_identities_hold and identity_holds

        print(
            f"n={n:2d}: F(n)={f_n:>12d}  F(n+1)={f_n1:>12d}  "
            f"F(2n)={f_2n:>12d}  identity holds: {identity_holds}"
        )

    print()
    print(f"Identity F(2n) = F(n)(2F(n+1) - F(n)) holds for all n in 0..{count - 1}: "
          f"{all_identities_hold}")

    if not all_identities_hold:
        raise AssertionError("Fibonacci doubling identity failed")


if __name__ == "__main__":
    main()
