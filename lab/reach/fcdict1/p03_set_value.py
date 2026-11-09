def main():
    d = {}
    d.setdefault('s', set()).add(3)
    d.setdefault('s', set()).add(3)
    d.setdefault('s', set()).add(4)
    print(len(d['s']), 3 in d['s'], 5 in d['s'])


main()
