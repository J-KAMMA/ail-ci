import math

def is_prime(n):
    if n < 2:
        return False
    limit = math.isqrt(n)
    factor = 2
    while factor <= limit:
        if n % factor == 0:
            return False
        factor += 1
    return True

def prime_gap(values):
    gap = 0
    for i in range(1, len(values)):
        gap = math.gcd(gap, values[i] - values[i - 1])
    return gap

def main():
    primes = [n for n in range(2, 60) if is_prime(n)]
    print("primes", primes)
    print("count", len(primes), "last", primes[-1], "root", math.isqrt(primes[-1]))
    print("gap", prime_gap(primes[:8]))
    print("lcm", math.lcm(4, 6), math.lcm(21, 6))
    print("pairs", math.comb(6, 2), math.perm(6, 2))
    print("product", math.prod(primes[:5]))
    print("gcd", math.gcd(48, 180))
    try:
        print(math.isqrt(-9))
    except ValueError as exc:
        print("isqrt failed:", exc)

main()
