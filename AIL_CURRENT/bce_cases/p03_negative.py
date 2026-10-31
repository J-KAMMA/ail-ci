def back(xs: list[int], k: int) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i - k]
    return s


def back2(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s = s * 3 + xs[-i - 1]
    return s


def main():
    xs = [1, 2, 3, 4, 5]
    for k in (0, 1, 2, 5, 6, -1, -3):
        try:
            print(k, back(xs, k))
        except IndexError as e:
            print(k, "IndexError", e)
    print(back2(xs))
    try:
        print(back2([]))
    except IndexError as e:
        print("IndexError", e)


main()
