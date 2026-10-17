import sys
from collections import Counter


def main() -> None:
    data = sys.stdin.read().splitlines()
    if not data:
        return
    n = int(data[0].strip())
    lines = data[1:1 + n]
    counts: Counter[str] = Counter()
    for line in lines:
        for ch in line:
            counts[ch] += 1
    result = {k: counts[k] for k in sorted(counts)}
    print(repr(result))


if __name__ == "__main__":
    main()
