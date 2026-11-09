def main():
    d = {}
    d.setdefault(1, [0, 0, 0])
    d.setdefault(1, [9, 9, 9])
    d[1][1] += 5
    print(d[1])


main()
