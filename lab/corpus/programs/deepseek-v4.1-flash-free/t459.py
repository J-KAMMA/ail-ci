import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    numbers = [int(token) for token in data[1 : 1 + n]]

    print(*numbers, sep=", ", end="\n")

    for value in numbers:
        sys.stdout.write(f"{value}\n")

    print(*numbers, sep="|")


if __name__ == "__main__":
    main()
