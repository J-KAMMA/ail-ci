import sys
from collections import Counter

BRACKETS = "()[]{}"


def main() -> None:
    lines = sys.stdin.read().splitlines()
    n = int(lines[0].strip()) if lines else 0
    counts: Counter[str] = Counter()
    for line in lines[1:1 + n]:
        for ch in line:
            if ch in BRACKETS:
                counts[ch] += 1
    result = {k: counts[k] for k in sorted(counts)}
    print(repr(result))


if __name__ == "__main__":
    main()
