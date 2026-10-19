import sys


def ugly_numbers(count: int) -> list[int]:
    """Return the first `count` ugly numbers using the three-pointer method."""
    if count <= 0:
        return []
    result: list[int] = [1]
    i2 = i3 = i5 = 0
    while len(result) < count:
        next2 = result[i2] * 2
        next3 = result[i3] * 3
        next5 = result[i5] * 5
        nxt = min(next2, next3, next5)
        result.append(nxt)
        if nxt == next2:
            i2 += 1
        if nxt == next3:
            i3 += 1
        if nxt == next5:
            i5 += 1
    return result


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    ugly = ugly_numbers(max(n, 15))
    print(ugly[n - 1])
    print(" ".join(str(x) for x in ugly[:15]))


if __name__ == "__main__":
    main()
