from __future__ import annotations


class CountingDict(dict[str, int]):
    def __missing__(self, key: str) -> int:
        return 0

    def __repr__(self) -> str:
        items = ", ".join(f"{key!r}: {value}" for key, value in sorted(self.items()))
        return "{" + items + "}"


def main() -> None:
    words = input().split()

    counts: CountingDict = CountingDict()
    for word in words:
        counts[word] = counts[word] + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for word, count in ranked[:3]:
        print(word, count)


if __name__ == "__main__":
    main()
