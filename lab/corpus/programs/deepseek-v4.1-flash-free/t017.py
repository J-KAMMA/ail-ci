import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]
    values.sort(reverse=True)
    total = 0
    for k in range(1, min(5, n) + 1):
        total += values[k - 1]
        print(total)


if __name__ == "__main__":
    main()
