"""Iterative Fibonacci to n = 50000, without recursion.

F(50000) has about 10450 decimal digits, well past int64.  The program prints
its last 40 decimal digits and its bit length (both stay small enough for the
4300-digit str() limit).
"""


def main() -> None:
    a = 0
    b = 1
    i = 0
    while i < 50000:
        c = a + b
        a = b
        b = c
        i = i + 1
    print(a % (10 ** 40))
    print(a.bit_length())


main()
