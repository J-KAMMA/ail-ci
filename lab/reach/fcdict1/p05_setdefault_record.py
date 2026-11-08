def main():
    d = {}
    p = d.setdefault('a', [0, 0, 0])
    p[0] += 1
    p[1] += 2
    p[2] += 3
    q = d.get('b', [0, 0, 0])
    q[0] += 7
    print(d['a'][0], d['a'][1], d['a'][2])
    print(q[0], q[1], q[2], len(d), 'b' in d)
main()
