import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    a: list[int] = [int(x) for x in data[1:1 + n]]

    print(a[::2])
    print(a[::-1])
    print(a[1:-1])
    print(a[-3:])

    a[1:3] = [0]
    print(a)

    del a[::2]
    print(a)


if __name__ == "__main__":
    main()
