from typing import Dict, List


def sign_label(n: int) -> str:
    if n < 0:
        return "neg"
    if n > 0:
        return "pos"
    return "zero"


def parity_label(n: int) -> str:
    return "odd" if n % 2 != 0 else "even"


def main() -> None:
    import sys

    tokens = sys.stdin.read().split()
    buckets: Dict[str, List[int]] = {}
    for token in tokens:
        n = int(token)
        key = f"{sign_label(n)}-{parity_label(n)}"
        buckets.setdefault(key, []).append(n)

    for key in sorted(buckets):
        print(f"{key}: {sorted(buckets[key])}")


if __name__ == "__main__":
    main()
