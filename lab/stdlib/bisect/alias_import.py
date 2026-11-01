import bisect as bs


def main():
    marks = [10, 20, 30, 40, 50]
    print(bs.bisect(marks, 30))
    print(bs.bisect_left(marks, 30))
    print(bs.bisect_right(marks, 30))
    bs.insort(marks, 35)
    bs.insort_left(marks, 35)
    bs.insort_right(marks, 35)
    print(marks)
    print(bs.bisect_left(marks, 35), bs.bisect_right(marks, 35))
    print(bs.bisect_left(marks, 35, 3), bs.bisect_right(marks, 35, 3, 7))


main()
