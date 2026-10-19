import heapq
import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return

    n: int = int(data[0])
    entries: list[tuple[str, float]] = []
    for i in range(n):
        name: str = data[1 + 2 * i]
        value: float = float(data[2 + 2 * i])
        entries.append((name, value))

    def by_value(entry: tuple[str, float]) -> float:
        return entry[1]

    top: list[tuple[str, float]] = heapq.nlargest(3, entries, key=by_value)
    bottom: list[tuple[str, float]] = heapq.nsmallest(3, entries, key=by_value)

    for name, value in top:
        print(f"{name} {value:.2f}")
    for name, value in bottom:
        print(f"{name} {value:.2f}")


if __name__ == "__main__":
    main()
