from collections import Counter, defaultdict


def main() -> int:
    xs = [1, 1, 2, 2, 3, 1]
    ys = [0, 0, 1, 1, 2, 0]
    freq = Counter(zip(xs, ys))
    print(freq)
    print(freq[(1, 0)], freq[(9, 9)], len(freq))
    for point, count in freq.most_common(2):
        print(point, count)
    freq[(1, 0)] += 3
    del freq[(9, 9)]
    print(sorted(freq.items()))
    other = Counter({(1, 0): 1, (7, 7): 4})
    print(sorted((freq + other).items()))
    print(sorted((freq - other).items()))
    print(sorted((freq & other).items()))
    print(sorted((freq | other).items()))
    rows: defaultdict[str, Counter[tuple[int, int]]] = defaultdict(Counter)
    for x, y in zip(xs, ys):
        rows["even" if (x + y) % 2 == 0 else "odd"][(x, y)] += 1
    for key in sorted(rows):
        print(key, sorted(rows[key].items()))
    totals: defaultdict[int, int] = defaultdict(int)
    for point in freq:
        totals[point[0] + point[1]] += freq[point]
    for key in sorted(totals):
        print(key, totals[key])
    return 0


main()
