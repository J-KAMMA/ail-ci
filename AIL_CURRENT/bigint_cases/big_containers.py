def main():
    big = 2**100
    xs = [big + i for i in range(5)]
    print(xs, sum(xs), max(xs) - min(xs), 7 ** 80 // 3 ** 90)
    d = {}
    for i in range(70):
        d[2**i] = i
    print(len(d), d[2**69], 2**64 in d, (2**64 + 1) in d)
    print(hash(2**64 - 2**64 + 5) == hash(5), hash(2**100) == hash(float(2**100)))
main()
