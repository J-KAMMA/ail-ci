import sys


def main() -> None:
    line = sys.stdin.read().split()
    buckets: dict[str, list[int]] = {}
    for token in line:
        n = int(token)
        sign = "neg" if n < 0 else "pos"
        parity = "odd" if n % 2 != 0 else "even"
        buckets.setdefault(f"{sign}-{parity}", []).append(n)
    for key in sorted(buckets):
        print(f"{key}: {sorted(buckets[key])}")


if __name__ == "__main__":
    main()
