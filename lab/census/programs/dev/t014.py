import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    values: list[int] = [int(x) for x in data[1:1 + n]]
    result: list[str] = []
    current: int | None = None
    for v in values:
        if current is None or v > current:
            current = v
        result.append(str(current))
    print(" ".join(result))


if __name__ == "__main__":
    main()
