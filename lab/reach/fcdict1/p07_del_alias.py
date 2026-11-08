def main():
    d = {}
    d['a'] = ['x', 1, True]
    v = d['a']
    del d['a']
    v[1] += 5
    print(v, len(d), 'a' in d)
main()
