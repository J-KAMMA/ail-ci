import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values: list[int] = [int(tok) for tok in data[1:1 + n]]

    changed = sum(1 for v in values if v < 0)
    result = [abs(v) for v in values]

    print(" ".join(str(v) for v in result))
    print(changed)


if __name__ == "__main__":
    main()
