from array import array


def main():
    raw = bytes([3, 0, 7, 2, 3, 1, 7, 7])
    counts = array('B', [0]) * 10
    for value in raw:
        counts[value] += 1
    print(counts)
    print(counts.tolist())
    print(sum(counts), max(counts), counts.index(max(counts)))
    print(counts[2:6])
    most = counts[:5]
    most.reverse()
    print(most)
    print(array('B', raw[:4]))
    for i, n in enumerate(counts):
        if n:
            print(i, n)


main()
