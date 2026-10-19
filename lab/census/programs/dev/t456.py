import sys


class WordCounter(dict[str, int]):
    """A Counter-like dict that returns 0 for missing words."""

    def __missing__(self, key: str) -> int:
        return 0

    def add(self, word: str) -> None:
        self[word] = self[word] + 1

    def most_common(self, n: int) -> list[tuple[str, int]]:
        ranked = sorted(self.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:n]

    def __repr__(self) -> str:
        return repr(dict(sorted(self.items())))


def main() -> None:
    line = sys.stdin.readline()
    words = line.split()

    counter = WordCounter()
    for word in words:
        counter.add(word)

    top = WordCounter(counter.most_common(3))
    print(top)


if __name__ == "__main__":
    main()
