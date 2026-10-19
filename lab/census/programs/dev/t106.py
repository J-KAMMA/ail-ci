import sys
from collections import Counter
import string


def main() -> None:
    text: str = sys.stdin.read()
    counts: Counter[str] = Counter(ch for ch in text if ch in string.ascii_lowercase)

    distinct: int = len(counts)
    missing: str = "".join(ch for ch in string.ascii_lowercase if counts[ch] == 0)

    most_frequent: str = ""
    if counts:
        best: int = max(counts.values())
        most_frequent = min(ch for ch, c in counts.items() if c == best)

    print(distinct)
    print(missing)
    print(most_frequent)


if __name__ == "__main__":
    main()
