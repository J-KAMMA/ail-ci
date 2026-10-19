def main() -> None:
    n = int(input().strip())

    # Factorize n to get its distinct prime factors.
    primes: list[int] = []
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            primes.append(p)
            while m % p == 0:
                m //= p
        p += 1
    if m > 1:
        primes.append(m)

    # Euler totient.
    phi = n
    for q in primes:
        phi = phi // q * (q - 1)

    # Squarefree divisors d with Mobius sign mu(d).
    divisors: list[tuple[int, int]] = [(1, 1)]
    for q in primes:
        divisors += [(d * q, -sign) for d, sign in divisors]

    # Inclusion-exclusion: count k in 1..n with gcd(k, n) = 1 and even digit sum.
    total = 0
    for d, sign in divisors:
        cnt = 0
        for k in range(d, n + 1, d):
            if sum(map(int, str(k))) % 2 == 0:
                cnt += 1
        total += sign * cnt

    print(phi, total)


if __name__ == "__main__":
    main()
