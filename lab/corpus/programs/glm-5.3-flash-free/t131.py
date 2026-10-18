import sys


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    values = [float(token) for token in data[2 : 2 + 2 * n : 2]]
    print(sum(round(value) for value in values))
    print(f"{sum(values):.2f}")


if __name__ == "__main__":
    main()
