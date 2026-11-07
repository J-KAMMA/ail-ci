def main():
    d = {}
    d['a'] = [0, 0, True]
    x = int('9223372036854775808')
    d['a'][1] = x
    print(d['a'])


main()
