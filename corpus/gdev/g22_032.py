# task: Implement a bit-packed Sieve of Eratosthenes using a bytearray for numbers up to 200 and print the primes found.
def is_set(bits: bytearray, n: int) -> bool:
    """Return True if bit n is set in the packed bit array."""
    return bool(bits[n >> 3] & (1 << (n & 7)))


def clear_bit(bits: bytearray, n: int) -> None:
    """Clear bit n in the packed bit array."""
    mask: int = 1 << (n & 7)
    bits[n >> 3] &= ~mask & 0xFF


def sieve_bitpacked(limit: int) -> bytearray:
    """
    Build a bit-packed Sieve of Eratosthenes up to and including `limit`.
    A set bit at position n means n is (still) a prime candidate.
    """
    size: int = limit // 8 + 1
    bits: bytearray = bytearray(b"\xff" * size)

    # 0 and 1 are not prime.
    clear_bit(bits, 0)
    clear_bit(bits, 1)

    i: int = 2
    while i * i <= limit:
        if is_set(bits, i):
            for multiple in range(i * i, limit + 1, i):
                clear_bit(bits, multiple)
        i += 1

    return bits


def main() -> None:
    limit: int = 200
    bits: bytearray = sieve_bitpacked(limit)

    primes: list[int] = [n for n in range(limit + 1) if is_set(bits, n)]

    print(f"Primes up to {limit}:")
    print(" ".join(str(p) for p in primes))
    print(f"Count: {len(primes)}")


if __name__ == "__main__":
    main()
