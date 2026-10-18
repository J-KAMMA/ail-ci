import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = [int(x) for x in data[1:1 + n]]
    changed = 0
    result = []
    for value in nums:
        if value < 0:
            changed += 1
            result.append(-value)
        else:
            result.append(value)
    print(" ".join(str(x) for x in result))
    print(changed)


if __name__ == "__main__":
    main()
