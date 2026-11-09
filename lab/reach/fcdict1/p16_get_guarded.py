def main():
    d = {}
    d[1] = [5, 450, True]
    if 1 in d:
        a = d.get(1)
        print(a[1])
    if 2 in d:
        b = d.get(2)
        print(b[0])
    print("done")


main()
