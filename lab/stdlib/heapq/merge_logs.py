import heapq


def main():
    morning = [(1, "boot"), (4, "sync"), (7, "backup")]
    midday = [(2, "alarm"), (5, "deploy")]
    evening = [(3, "audit"), (6, "rollover"), (8, "shutdown")]
    merged = heapq.merge(morning, midday, evening)
    for stamp, event in merged:
        print(stamp, event)

    left = [(1, "a"), (3, "c")]
    right = [(0, "z"), (2, "b")]
    print("key", list(heapq.merge(left, right, key=lambda row: row[0])))

    down_a = [5, 3, 1]
    down_b = [6, 4, 2]
    print("reverse", list(heapq.merge(down_a, down_b, reverse=True)))

    empty = []
    print("empty", list(heapq.merge(empty, [9, 10])))
    print("steady", list(heapq.merge([1, 1, 2], [1, 2, 2])))


main()
