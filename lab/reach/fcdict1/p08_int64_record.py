def main():
    d = {}
    d[1] = [0, 0, True]
    v = d[1]
    v[0] = 9223372036854775807
    v[0] = v[0] + 1
    print(v[0])


main()
