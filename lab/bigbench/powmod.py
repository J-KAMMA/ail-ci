"""300 modular exponentiations with 1024-bit bases, exponents and moduli.

The three operands of each call are built from a fixed 64-bit LCG (three draws
per 64-bit limb, 16 limbs = 1024 bits).  `pow(b, e, m)` is CPython's modular
square-and-multiply; the checksum folds every result with xor and prints it
modulo 10^50.
"""


def main() -> None:
    state = 123456789
    total = 0
    i = 0
    while i < 300:
        b = 0
        e = 0
        m = 0
        j = 0
        while j < 16:
            state = (state * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
            b = (b << 64) + state
            state = (state * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
            e = (e << 64) + state
            state = (state * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
            m = (m << 64) + state
            j = j + 1
        m = m | 1
        total = total ^ pow(b, e, m)
        i = i + 1
    print(total % (10 ** 50))


main()
