import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    numbers: list[int] = [int(tok) for tok in data[1:1 + n]]
    numbers.sort(key=lambda x: (bin(x).count("1"), x))
    print(" ".join(map(str, numbers)))


if __name__ == "__main__":
    main()
