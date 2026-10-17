import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = map(int, data[1:1 + n])

    running_max: int | None = None
    result: list[str] = []
    for x in nums:
        if running_max is None or x > running_max:
            running_max = x
        result.append(str(running_max))

    sys.stdout.write(" ".join(result))


if __name__ == "__main__":
    main()
