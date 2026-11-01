import bisect


def main():
    values = [1, 2, 2, 3]
    empty = []
    print("empty", bisect.bisect_left(empty, 1), bisect.bisect_right(empty, 1))
    print("neg", bisect.bisect_left(values, 2, 0, -1), bisect.bisect_right(values, 2, 0, -2))
    print("none", bisect.bisect_left(values, 2, 0, None), bisect.bisect_right(values, 2, hi=None))
    print("order", bisect.bisect_left(values, 2, 3, 1), bisect.bisect_right(values, 2, 3, 1))
    try:
        bisect.bisect_left(values, 2, -1)
    except ValueError as error:
        print("lo", error)
    try:
        bisect.bisect_right(values, 2, 0, 99)
    except IndexError as error:
        print("hi", error)
    try:
        bisect.insort(values, 2, 0, 99)
    except IndexError as error:
        print("insort", error)
    extra = [1, 3, 5]
    bisect.insort(extra, 4, 0, -1)
    print("insert", extra)


main()
