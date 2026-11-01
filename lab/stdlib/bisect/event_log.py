import bisect


def main():
    times = []
    for stamp in [5, 12, 12, 19, 27, 33, 41, 55]:
        bisect.insort(times, stamp)
    queries = [(0, 10), (12, 12), (20, 40), (55, 60)]
    for start, end in queries:
        left = bisect.bisect_left(times, start)
        right = bisect.bisect_right(times, end)
        print(start, end, right - left, times[left:right])
    low = 2
    high = len(times) - 1
    print("window", bisect.bisect_left(times, 12, low, high), bisect.bisect_right(times, 12, lo=low, hi=high))
    print("tail", bisect.bisect_right(times, 12, 4), bisect.bisect_left(times, 12, hi=5))
    print("all", bisect.bisect_left(times, 12, 0, None), bisect.bisect_right(times, 12, hi=None))


main()
