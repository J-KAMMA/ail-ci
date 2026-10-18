import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    a = [int(x) for x in data[1:1 + n]]

    print(*a[::2])
    print(*a[::-1])
    print(*a[1:-1])
    print(*a[-3:])

    a[1:3] = [0]
    print(*a)

    del a[::2]
    print(*a)


if __name__ == "__main__":
    main()
