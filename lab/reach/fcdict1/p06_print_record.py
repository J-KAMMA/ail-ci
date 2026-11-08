def main():
    d = {}
    d['a'] = ['alice', 100, True]
    d['b'] = ['bob', 40, False]
    v = d['a']
    print(v)
    print([d['a'][0], d['a'][1], d['a'][2]])
    print(d)
main()
