def main():
    d = {}
    d['a'] = set()
    d['a'].add(1)
    s = d['a']
    s.add(2)
    s.add(2)
    print(len(d['a']), 1 in d['a'], 3 in d['a'])
    for x in d['a']:
        print(x)


main()
