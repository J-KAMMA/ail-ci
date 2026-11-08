def main():
    d = {}
    d.setdefault('a', set()).add(1)
    d.setdefault('a', set()).add(1)
    d.setdefault('a', set()).add(4)
    v = d['a']
    v.add(9)
    print(len(d['a']), 9 in v, sorted(d['a']))
main()
