import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values: list[int] = [int(x) for x in data[1:1 + n]]
    if not values:
        return
    global_max = max(values)
    # The first occurrence of the global maximum is strictly larger than all
    # previous elements (none of them equal the maximum), so it is the target index.
    first_index = values.index(global_max)
    count = values.count(global_max)
    print(first_index, count)


if __name__ == "__main__":
    main()
