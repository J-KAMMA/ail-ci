import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = list(map(int, data[1:1 + n]))
    numbers.sort(key=lambda x: (bin(x).count("1"), x))
    sys.stdout.write(" ".join(map(str, numbers)) + "\n")


if __name__ == "__main__":
    main()
