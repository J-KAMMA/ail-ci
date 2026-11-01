import bisect


def contains(values, target):
    pos = bisect.bisect_left(values, target)
    return pos < len(values) and values[pos] == target


def insert_all(values, items):
    for item in items:
        bisect.insort_right(values, item)
    return values


def main():
    values = insert_all([], [7, 3, 5, 3, 9, 1])
    print("values", values)
    for target in [0, 1, 3, 4, 9, 10]:
        print(target, contains(values, target))
    left = bisect.bisect_left(values, 3)
    right = bisect.bisect_right(values, 3)
    print("dups", left, right, values[left:right])
    print("bisect", bisect.bisect(values, 5), bisect.bisect(values, 6))


main()
