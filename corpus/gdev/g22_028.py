# task: Generate the binary de Bruijn sequence B(2,4) using the standard Lyndon word algorithm and print it.
from typing import List


def de_bruijn(k: int, n: int) -> List[int]:
    """Generate a de Bruijn sequence B(k, n) using the Lyndon word algorithm
    (Duval's / FKM algorithm)."""
    a: List[int] = [0] * (k * n)
    sequence: List[int] = []

    def db(t: int, p: int) -> None:
        if t > n:
            if n % p == 0:
                sequence.extend(a[1 : p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)
    return sequence


def main() -> None:
    k: int = 2
    n: int = 4
    seq: List[int] = de_bruijn(k, n)
    print("".join(str(symbol) for symbol in seq))


if __name__ == "__main__":
    main()
