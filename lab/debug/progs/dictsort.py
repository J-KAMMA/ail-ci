def main() -> None:
    counts = {}
    for i in range(6):
        counts[i % 3] = i
    best = 0
    for key in sorted(counts):
        if counts[key] > best:
            best = counts[key]
    print(best, len(counts))
    total = 0
    for key in counts:
        total += counts[key]
    print(total)
    print(str(-7), abs(-7), max(3, 9), min(3, 9))
    f = 1.5
    g = f * 2.0
    print(g)


main()
