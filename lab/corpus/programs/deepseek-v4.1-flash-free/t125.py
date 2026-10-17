import sys
from collections import Counter

BUCKETS = list(range(0, 101, 10))


def main() -> None:
    tokens = sys.stdin.read().split()
    if not tokens:
        return

    n = int(tokens[0])
    counts: Counter[int] = Counter()

    i = 1
    for _ in range(n):
        _name = tokens[i]
        score = int(tokens[i + 1])
        i += 2
        bucket = 100 if score == 100 else (score // 10) * 10
        counts[bucket] += 1

    for bucket in BUCKETS:
        count = counts.get(bucket, 0)
        if count == 0:
            continue
        label = "100" if bucket == 100 else f"{bucket}-{bucket + 9}"
        print(f"{label}: {'#' * count}")


if __name__ == "__main__":
    main()
