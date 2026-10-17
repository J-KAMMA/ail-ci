import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return

    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]
    present = set(values)

    pairs = [(v, -v) for v in present if v < 0 and -v in present]
    pairs.sort()

    if not pairs:
        print("none")
    else:
        for a, b in pairs:
            print(f"{a} {b}")


if __name__ == "__main__":
    main()
