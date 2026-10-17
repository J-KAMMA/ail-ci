import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return
    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]
    distinct = sorted(set(values), reverse=True)
    if len(distinct) >= 2:
        print(distinct[1])
    else:
        print("none")


if __name__ == "__main__":
    main()
