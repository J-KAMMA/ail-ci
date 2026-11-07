def main():
    d = {}
    d['a'] = [0, 0, True]
    d['a'][0] = 4
    d['a'][1] = d['a'][0] + 1
    d['a'][2] = False
    print(d['a'])
    print(d['a'][2])


main()
