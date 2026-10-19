import sys
from collections import Counter


def main() -> None:
    words: list[str] = sys.stdin.read().split()

    counts: Counter[str] = Counter(words)
    distinct_count: int = len(counts)

    first_repeated: str | None = None
    seen: set[str] = set()
    for word in words:
        if word in seen:
            first_repeated = word
            break
        seen.add(word)

    unique_once: list[str] = []
    emitted: set[str] = set()
    for word in words:
        if counts[word] == 1 and word not in emitted:
            unique_once.append(word)
            emitted.add(word)

    print(distinct_count)
    print(first_repeated if first_repeated is not None else "none")
    print(" ".join(unique_once))


if __name__ == "__main__":
    main()
