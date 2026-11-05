"""Sieve of Eratosthenes: count and sum the primes below N."""
import sys

SMALL = "--small" in sys.argv
N = 50_000 if SMALL else 11_000_000


def sieve(limit):
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = 0
    is_prime[1] = 0
    p = 2
    while p * p <= limit:
        if is_prime[p]:
            multiple = p * p
            while multiple <= limit:
                is_prime[multiple] = 0
                multiple += p
        p += 1
    return is_prime


flags = sieve(N)
count = 0
total = 0
largest = 0
for number in range(N + 1):
    if flags[number]:
        count += 1
        total += number
        largest = number

print("limit", N)
print("primes", count)
print("sum", total)
print("largest", largest)
