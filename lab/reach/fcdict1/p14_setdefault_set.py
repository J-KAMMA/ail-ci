def main():
    d = {}
    d.setdefault('a', set()).add(1)
    d.setdefault('a', set()).add(1)
    d.setdefault('a', set()).add(4)
    d.setdefault('b', set()).add(2)
    print(len(d['a']), 1 in d['a'], 3 in d['a'])
    s = d['a']
    s.add(5)
    print(sorted(d['a']))
    print(sorted(d['b']))


main()
