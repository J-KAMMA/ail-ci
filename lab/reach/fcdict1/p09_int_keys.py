def main():
    d = {}
    d[7] = [10, 20, True]
    d[9] = [30, 40, False]
    r = d.get(7)
    r[0] += 1
    print(d[7][0], d[9][1], d[7][2])
    print(sum(a[1] for a in d.values() if a[2]))
    for k, (a, b, s) in d.items():
        print(k, a, b, s)


main()
