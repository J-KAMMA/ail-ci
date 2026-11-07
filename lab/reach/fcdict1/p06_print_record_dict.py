def main():
    d = {}
    d['a'] = [3, 450, True]
    d['b'] = [4, 500, False]
    print(d['a'])
    print(d)
    v = d['a']
    print(v)
    v[2] = False
    print(d['a'])
    print(v)


main()
