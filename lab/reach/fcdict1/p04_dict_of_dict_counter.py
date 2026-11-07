def main():
    d = {}
    d['a'] = {}
    d['a'][1] = 2
    d['a'][1] += 3
    v = d['a']
    v[2] = 7
    print(d['a'][1], v[2], len(d['a']))


main()
