def main():
    d = {}
    d[1] = [10, 20, 30]
    v = d[1]
    del d[1]
    v[0] = 99
    print(v)
    print(d)


main()
