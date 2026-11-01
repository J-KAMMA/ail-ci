import bisect


def build_index(words):
    index = []
    for word in words:
        bisect.insort_left(index, word)
    return index


def main():
    words = ["pear", "apple", "fig", "banana", "apple", "date", "fig"]
    index = build_index(words)
    print("index", ",".join(index))
    for query in ["apple", "cherry", "fig", "kiwi"]:
        pos = bisect.bisect_left(index, query)
        found = pos < len(index) and index[pos] == query
        print(query, pos, found)
    bisect.insort(index, "cherry")
    print("after", ",".join(index))
    print("range", bisect.bisect_left(index, "fig"), bisect.bisect_right(index, "fig"))
    print("window", bisect.bisect_left(index, "fig", 2, 6), bisect.bisect_right(index, "fig", lo=2, hi=6))


main()
