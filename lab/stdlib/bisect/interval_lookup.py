import bisect


def main():
    edges = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]
    labels = ["zero", "half", "one", "two", "four", "eight", "above"]
    samples = [-1.0, 0.0, 0.25, 0.5, 0.99, 1.0, 3.5, 8.0, 12.5]
    for value in samples:
        index = bisect.bisect_right(edges, value)
        print(f"{value:.2f}", labels[index])
    values = [1.5, 0.5, 2.5, 1.5, 0.5]
    bisect.insort_left(values, 1.0)
    bisect.insort_right(values, 1.0)
    print("sorted", values)
    print("left", bisect.bisect_left(values, 1.0), "right", bisect.bisect_right(values, 1.0))
    print("empty", bisect.bisect_left([], 1.0), bisect.bisect_right([], 1.0))


main()
