def main():
    d = {}
    d.setdefault('a', [0, 0, 0])
    d.setdefault('a', [0, 0, 0])
    d['a'][0] += 1
    r = d.get('a')
    r[1] += 5
    d.setdefault('b', [0, 0, 0])
    d['b'][2] += 1
    print(d['a'][0], d['a'][1], d['a'][2])
    print(d['b'][0], d['b'][1], d['b'][2])


main()
