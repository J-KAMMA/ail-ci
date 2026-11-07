def main():
    d = {}
    d['a'] = [1, 2, True]
    v = d['a']
    del d['a']
    v[1] = 9
    print(v)
    print(len(d))
    d['a'] = [7, 8, True]
    print(d['a'])
    print(v)


main()
