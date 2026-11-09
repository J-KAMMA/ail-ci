def main():
    d = {}
    d[1] = [1, 2, 3]
    x = d.get(1)
    x[1] = 20
    print(d[1])
    print(x[1])


main()
