def risky(n: int) -> int:
    xs = [10, 20, 30]
    return xs[n]


def main() -> None:
    total = 0
    for i in range(4):
        try:
            total += risky(i)
        except IndexError:
            total += 1000
        else:
            total += 1
        finally:
            total += 2
    try:
        v = 10 // 0
    except ZeroDivisionError:
        v = -1
    print(total, v)


main()
