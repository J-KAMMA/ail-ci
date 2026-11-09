def main():
    d = {}
    d[1] = [1, 2, 3]
    x = d.get(2)
    print(x is None)


main()
