import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = data[1:1 + n]

    seen: set[str] = set()
    result: list[str] = []
    for value in numbers:
        if value not in seen:
            seen.add(value)
            result.append(value)

    sys.stdout.write(" ".join(result) + "\n")


if __name__ == "__main__":
    main()
