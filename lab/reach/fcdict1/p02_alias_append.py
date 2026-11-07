def main():
    d = {}
    d['a'] = [1, 2]
    v = d['a']
    v.append(3)
    print(v)
    print(d['a'])
    d['a'].append(4)
    print(v)


main()
