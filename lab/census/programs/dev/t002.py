import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    numbers: list[int] = [int(x) for x in data[1:1 + n]]
    ascending: list[int] = sorted(numbers)
    descending: list[int] = sorted(numbers, reverse=True)
    print(" ".join(str(x) for x in ascending))
    print(" ".join(str(x) for x in descending))


if __name__ == "__main__":
    main()
