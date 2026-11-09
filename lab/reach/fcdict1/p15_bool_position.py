def main():
    d = {}
    d[1] = [5, 450, True]
    a = d[1]
    a[2] = False
    print(d[1])
    print(a[2])


main()
