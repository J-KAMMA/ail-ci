import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    numbers: list[int] = [int(tok) for tok in data[1:1 + n]]
    result: list[int] = sorted(numbers, key=lambda x: (x % 10, -x))
    print(" ".join(str(x) for x in result))


if __name__ == "__main__":
    main()
