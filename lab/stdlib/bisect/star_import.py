from bisect import *


def main():
    values = []
    for value in [3, 1, 4, 1, 5, 9, 2, 6]:
        insort(values, value)
    print(values)
    print(bisect_left(values, 4), bisect_right(values, 4), bisect(values, 4))
    insort_left(values, 4)
    insort_right(values, 4)
    print(values)
    print(bisect_left(values, 4), bisect_right(values, 4))
    print(bisect_left(values, 0), bisect_right(values, 9))


main()
