def main():
    d = {}
    d['a'] = [1, 2, True]
    r = d.get('b', [0, 0, False])
    print(r[0], r[1], r[2])
    print(d['a'][0])
    print(len(d))
    q = d.get('a', [0, 0, False])
    q[0] = 5
    print(d['a'][0])


main()
