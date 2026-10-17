import sys


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]
    values.sort()

    if n % 2 == 1:
        print(values[n // 2])
    else:
        mid = n // 2
        print(f"{(values[mid - 1] + values[mid]) / 2:.1f}")


if __name__ == "__main__":
    main()
