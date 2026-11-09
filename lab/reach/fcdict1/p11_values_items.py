def main():
    d = {}
    d[1] = [10, 2, True]
    d[2] = [20, 3, False]
    print(sum(a[1] for a in d.values() if a[2]))
    for k, a in d.items():
        print(k, a[0], a[1], a[2])


main()
