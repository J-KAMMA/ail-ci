import sys


def parse_line(line: str) -> list[int]:
    return [int(tok) for tok in line.split()]


def main() -> None:
    data = sys.stdin.read().split("\n")
    first = data[0] if len(data) > 0 else ""
    second = data[1] if len(data) > 1 else ""

    a = parse_line(first)
    b = parse_line(second)

    pairs = list(zip(a, b))
    sums = [x + y for x, y in pairs]
    products = [x * y for x, y in pairs]
    dot = sum(products)

    print(" ".join(map(str, sums)))
    print(" ".join(map(str, products)))
    print(dot)


if __name__ == "__main__":
    main()
