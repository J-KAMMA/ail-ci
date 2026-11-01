import heapq


def smallest_range(lists):
    combined = heapq.merge(*lists)
    values = list(combined)
    if not values:
        return None
    return (values[0], values[-1])


def main():
    rows = [[1, 4, 7], [2, 5, 8], [3, 6, 9], [0, 10]]
    print("merged", list(heapq.merge(*rows)))
    span = smallest_range(rows)
    print("range", span)
    print("empty", smallest_range([]))

    latest = [[9, 5, 1], [8, 4, 2], [7, 3]]
    print("latest", list(heapq.merge(*latest, reverse=True)))

    keyed = [[(2, "b"), (4, "d")], [(1, "a"), (3, "c")]]
    print("keyed", list(heapq.merge(*keyed, key=lambda pair: pair[0])))

    selected = heapq.nsmallest(4, heapq.merge(*rows))
    print("selected", selected)
    top = heapq.nlargest(3, heapq.merge(*rows))
    print("top", top)


main()
